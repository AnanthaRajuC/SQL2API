#!/usr/bin/env python3
"""Buffered-vs-streamed benchmark, one dialect per invocation. See benchmarks/README.md for methodology
and how to read the numbers; run with --help for options.

Run manually, never from CI on push/PR - a maintainer fires this before a release or when a driver
changes. Needs a reachable database (env var per dialect, see below) and, for mysql/postgres/clickhouse/h2,
a Java runtime only for h2 (the others need just their Python driver, already part of queryapigate[all]).

Connection env vars (JSON, same shape tests/test_integration.py uses):
    QUERYAPIGATE_IT_MYSQL       {"host": ..., "port": ..., "user": ..., "password": ..., "database": ...}
    QUERYAPIGATE_IT_POSTGRES    same shape
    QUERYAPIGATE_IT_CLICKHOUSE  same shape
    QUERYAPIGATE_IT_H2          same shape
sqlite and duckdb need no server - a scratch file is created automatically.
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import dataset  # noqa: E402,I001
from queryapigate import __version__ as queryapigate_version  # noqa: E402,I001

RESULTS_DIR = Path(__file__).parent / 'results'
SAMPLE_INTERVAL = 0.2  # seconds between RSS samples while a request is in flight


# --------------------------------------------------------------------------------------
# Native connections, for seeding only - the benchmark itself always goes through the
# real HTTP API, but seeding a million rows through /execute_sql would itself dominate
# the clock, so setup uses each driver directly, the same way the seed took shape during
# manual testing (see runners.py's driver docstrings for the memory findings that grew
# out of that same manual testing).
# --------------------------------------------------------------------------------------

def native_connect(dialect, details):
    if dialect == 'mysql':
        import mysql.connector
        return mysql.connector.connect(host=details['host'], port=details.get('port', 3306),
                                       user=details['user'], password=details.get('password', ''),
                                       database=details['database'])
    if dialect == 'postgres':
        import psycopg2
        return psycopg2.connect(host=details['host'], port=details.get('port', 5432), user=details['user'],
                                password=details.get('password', ''), dbname=details['database'])
    if dialect == 'clickhouse':
        from clickhouse_driver import Client
        return Client(host=details['host'], port=details.get('port', 9000), user=details.get('user', 'default'),
                     password=details.get('password', ''), database=details.get('database', 'default'))
    if dialect == 'h2':
        import jaydebeapi  # noqa: I001

        from queryapigate import config
        host = details['host']
        if details.get('port'):
            host = f"{host}:{details['port']}"
        url = f"jdbc:h2:tcp://{host}/~/{details['database']}"
        return jaydebeapi.connect('org.h2.Driver', url, [details.get('user', 'SA'), details.get('password', '')],
                                  [config.h2_jar()])
    raise ValueError(f'native_connect() does not handle {dialect!r} (file-based dialects are seeded directly)')


def native_close(dialect, conn):
    if dialect == 'clickhouse':
        conn.disconnect()
    else:
        conn.close()


# --------------------------------------------------------------------------------------
# The queryapigate server under test: a real subprocess, hit over real HTTP, same as a user
# would - not the Flask test client, which does not exercise a real WSGI response cycle
# or a real separate OS process to sample memory from.
# --------------------------------------------------------------------------------------

class Server:
    def __init__(self, home, port, max_page_size):
        self.port = port
        env = {**os.environ, 'QUERYAPIGATE_HOME': str(home), 'QUERYAPIGATE_MAX_PAGE_SIZE': str(max_page_size)}
        env.pop('QUERYAPIGATE_API_KEY', None)
        self.proc = subprocess.Popen(
            [sys.executable, '-m', 'queryapigate', 'serve', '--port', str(port), '--host', '127.0.0.1'],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._wait_healthy()

    def _wait_healthy(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health', timeout=1)
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        raise RuntimeError('queryapigate server did not become healthy in time')

    def rss_mb(self):
        with open(f'/proc/{self.proc.pid}/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
        return None

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class Sampler:
    """Samples the server's RSS on a background thread while one request is in flight."""

    def __init__(self, server):
        self.server = server
        self.samples = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            rss = self.server.rss_mb()
            if rss is not None:
                self.samples.append(rss)
            self._stop.wait(SAMPLE_INTERVAL)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)


# --------------------------------------------------------------------------------------
# One HTTP request, timed and sampled.
# --------------------------------------------------------------------------------------

def run_request(server, sql, connection_name, stream, page_size=None):
    query = 'stream=true&format=csv' if stream else f'format=csv&page_size={page_size}'
    url = f'http://127.0.0.1:{server.port}/execute_sql?{query}'
    body = json.dumps({'sql': sql, 'connection_name': connection_name}).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')

    baseline = server.rss_mb()
    with Sampler(server) as sampler:
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=600) as res:
            total_bytes = 0
            rows = -1  # header line does not count as a row
            for chunk in iter(lambda: res.read(1 << 20), b''):
                total_bytes += len(chunk)
                rows += chunk.count(b'\n')
        elapsed = time.monotonic() - started

    peak = max(sampler.samples) if sampler.samples else server.rss_mb()
    return {
        'elapsed_s': elapsed,
        'rows': rows,
        'bytes': total_bytes,
        'rss_baseline_mb': baseline,
        'rss_peak_mb': peak,
        'rss_delta_mb': peak - baseline,
        'rss_samples': len(sampler.samples),
    }


def summarize(results):
    def stats(key):
        values = [r[key] for r in results]
        return {'median': statistics.median(values), 'min': min(values), 'max': max(values)}

    return {
        'repeats': len(results),
        'elapsed_s': stats('elapsed_s'),
        'rss_delta_mb': stats('rss_delta_mb'),
        'rss_peak_mb': stats('rss_peak_mb'),
        'rows': results[0]['rows'],
        'bytes': results[0]['bytes'],
    }


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def get_connection_details(dialect):
    if dialect in ('sqlite', 'duckdb'):
        return None
    raw = os.environ.get(f'QUERYAPIGATE_IT_{dialect.upper()}')
    if not raw:
        raise SystemExit(f'QUERYAPIGATE_IT_{dialect.upper()} is not set - see benchmarks/run.py --help')
    return json.loads(raw)


def build_connections_file(home, dialect, details, file_path=None):
    if dialect == 'sqlite':
        entry = {'db': 'sqlite', 'database': file_path, 'active': True}
    elif dialect == 'duckdb':
        entry = {'db': 'duckdb', 'database': file_path, 'active': True}
    else:
        entry = {'db': dialect, 'host': details['host'], 'port': details.get('port'), 'user': details.get('user'),
                 'password': details.get('password', ''), 'database': details['database'], 'active': True}
    with open(home / 'db_connections.json', 'w') as f:
        json.dump({'connections': {'bench': entry}}, f)


def seed(dialect, details, home, rows, width):
    width_chars = dataset.WIDTHS[width]
    if dialect == 'sqlite':
        import sqlite3
        path = home / 'bench.db'
        conn = sqlite3.connect(str(path))
        dataset.seed_sqlite(conn, rows, width_chars)
        conn.close()
        return str(path)
    if dialect == 'duckdb':
        import duckdb
        path = home / 'bench.duckdb'
        conn = duckdb.connect(str(path))
        dataset.seed_duckdb(conn, rows, width_chars)
        conn.close()
        return str(path)
    conn = native_connect(dialect, details)
    try:
        dataset.SEEDERS[dialect](conn, rows, width_chars)
    finally:
        native_close(dialect, conn)
    return None


def run_dialect(dialect, rows, widths, repeats, port):
    details = get_connection_details(dialect)
    print(f'== {dialect} ==  rows={rows:,}  widths={widths}  repeats={repeats}')

    with tempfile.TemporaryDirectory() as home_str:
        home = Path(home_str)
        report = {
            'dialect': dialect, 'rows': rows, 'repeats': repeats, 'queryapigate_version': queryapigate_version,
            'host': platform.platform(), 'cpu_count': os.cpu_count(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'scenarios': {},
        }
        for width in widths:
            print(f'  seeding {width} ({dataset.WIDTHS[width]}-char payload)...', flush=True)
            file_path = seed(dialect, details, home, rows, width)
            build_connections_file(home, dialect, details, file_path)

            server = Server(home, port, max_page_size=rows + 10)
            try:
                for mode in ('buffered', 'streamed'):
                    print(f'  {width}/{mode}: ', end='', flush=True)
                    results = []
                    for _ in range(repeats):
                        result = run_request(server, 'SELECT * FROM bench_data ORDER BY id', 'bench',
                                             stream=(mode == 'streamed'),
                                             page_size=rows if mode == 'buffered' else None)
                        results.append(result)
                        print(f'{result["elapsed_s"]:.2f}s/{result["rss_delta_mb"]:.0f}MB ', end='', flush=True)
                    print()
                    report['scenarios'][f'{width}/{mode}'] = summarize(results)
            finally:
                server.stop()
    return report


def render_markdown(report):
    lines = [
        f"# Benchmark: {report['dialect']}", '',
        f"- queryapigate {report['queryapigate_version']}, {report['timestamp']}",
        f"- {report['host']}, {report['cpu_count']} CPUs",
        f"- {report['rows']:,} rows, {report['repeats']} repeats per scenario (median/min/max shown)", '',
        '| Scenario | Latency (s) | Peak RSS delta (MB) | Rows | Bytes |',
        '|---|---|---|---|---|',
    ]
    for name, s in report['scenarios'].items():
        lat = s['elapsed_s']
        rss = s['rss_delta_mb']
        lines.append(f"| {name} | {lat['median']:.2f} ({lat['min']:.2f}-{lat['max']:.2f}) "
                     f"| {rss['median']:.0f} ({rss['min']:.0f}-{rss['max']:.0f}) | {s['rows']:,} | {s['bytes']:,} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('dialect', choices=sorted(dataset.SEEDERS))
    parser.add_argument('--rows', type=int, default=1_000_000)
    parser.add_argument('--widths', default='narrow,wide')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--port', type=int, default=5300)
    args = parser.parse_args()
    widths = args.widths.split(',')

    report = run_dialect(args.dialect, args.rows, widths, args.repeats, args.port)

    RESULTS_DIR.mkdir(exist_ok=True)
    date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out_path = RESULTS_DIR / f'{args.dialect}-{date}.md'
    out_path.write_text(render_markdown(report))
    print(f'\nWrote {out_path}')
    print(render_markdown(report))


if __name__ == '__main__':
    main()
