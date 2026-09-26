# Benchmarks

Buffered-vs-streamed (`?stream=true`, see [Streaming exports](../documentation/API.md#streaming-exports))
measured against real databases, one dialect at a time. This is **not** wired into CI - it is run manually,
on demand, before a release or when a driver changes, never on every push/PR (a memory/timing measurement on
a shared CI runner is exactly the kind of thing that's flaky, and pulling database images on every push would
slow down every PR for something that only needs checking occasionally).

## Why not a standard benchmark (TPC-H, sysbench, ...)?

TPC-H/TPC-DS benchmark a query engine's join and aggregation performance - not what changed here. This
benchmark exists to answer one question: how does a flat `SELECT` over N rows of width W behave buffered
versus streamed, per dialect? That's closer to what sysbench's simple synthetic tables are for, so
`dataset.py` builds one small, purpose-built table in that spirit rather than adopting a schema designed to
stress a query planner we didn't touch.

## The table

One table (`bench_data`: `id INT`, `payload` a string), two independently-controlled knobs:

- **Row count** - the scale factor. Defaults to 1,000,000; pass `--rows` for a different scale.
- **Row width** - `narrow` (~40-byte payload) or `wide` (~480-byte payload), since row width is the other
  real variable affecting buffered memory per row and it's easy to leave uncontrolled by accident.

Content is deterministic (not random), so seeding is fast and a run is reproducible.

## Methodology

- **One dialect at a time, sequentially, in its own process.** Noisy neighbors (another DB container
  competing for the host's CPU/disk/page cache) and a dirty baseline (a previous run's memory still resident
  in the same process) both showed up as real distortion during manual testing before this script existed -
  see the git history of `runners.py`'s driver docstrings for what that looked like.
- **A real subprocess, hit over real HTTP** - not the Flask test client, so there's an actual separate OS
  process whose RSS (`/proc/<pid>/status`) can be sampled every 0.2s while a request is in flight, the same
  way a user would actually experience it.
- **The "buffered" comparison needs `QUERYAPIGATE_MAX_PAGE_SIZE` raised** for the run - by design, you cannot
  normally request 1,000,000 rows in one page; the server is started with the cap raised specifically so the
  comparison point exists at all. That is itself part of the finding: without streaming, matching what
  streaming gives you for free means disabling the safety limit that protects you from doing this by
  accident.
- **N=5 repeats per scenario** (configurable via `--repeats`); the report shows median, min and max, not a
  single run.
- **Absolute numbers are machine-specific; the shape is the portable claim.** "Peak RSS delta stays flat as
  rows grow" survives a different machine - a specific megabyte figure doesn't. Read the numbers here as
  illustrative of the shape, not as a promise about any particular deployment's memory use.

## Running it

Needs a reachable database. sqlite and duckdb need nothing extra (a scratch file is created automatically);
the others read the same `QUERYAPIGATE_IT_*` JSON connection env vars `tests/test_integration.py` uses:

~~~bash
export QUERYAPIGATE_IT_MYSQL='{"host": "127.0.0.1", "port": 3306, "user": "root", "password": "pw", "database": "it"}'
python benchmarks/run.py mysql
python benchmarks/run.py mysql --rows 100000 --widths narrow --repeats 3   # a smaller, faster run
~~~

Each run writes `benchmarks/results/<dialect>-<date>.md` and prints the same report to the terminal. Commit
the result files that matter so the numbers stay checked in and dated - a benchmark nobody has rerun in six
months is worse for credibility than no benchmark at all if it's read as current.

## Results

| Dialect | Last run | Notes |
|---|---|---|
| MySQL | 2026-09-24 | Memory flat regardless of row width (~0MB streamed vs. 337-988MB buffered); streaming is 2-4x slower in latency than buffered for the same data - see [results/mysql-2026-09-24.md](results/mysql-2026-09-24.md) |
| PostgreSQL | 2026-09-24 | Memory flat regardless of row width (~0MB streamed vs. 352-928MB buffered); streaming is 2-5x slower in latency than buffered for the same data - see [results/postgres-2026-09-24.md](results/postgres-2026-09-24.md) |
| ClickHouse | 2026-09-24 | Memory flat regardless of row width (~0MB streamed vs. 348-1233MB buffered); streaming is 2-5x slower in latency than buffered for the same data - see [results/clickhouse-2026-09-24.md](results/clickhouse-2026-09-24.md) |
| SQLite | 2026-09-24 | Memory flat regardless of row width (~0MB streamed vs. 333-1034MB buffered), matching the network dialects despite no special unbuffered-cursor code - just the same fetchmany() loop, relying on SQLite's naturally incremental cursor; streaming is 2-4x slower in latency than buffered - see [results/sqlite-2026-09-24.md](results/sqlite-2026-09-24.md) |
| H2 | 2026-09-24 | Memory flat regardless of row width (~0MB streamed vs. 206-1062MB buffered); latency pattern *reverses* by width - streaming is slower for narrow rows (24.7s vs 19.9s) but faster for wide rows (54.0s vs 65.1s), unlike every other dialect - see [results/h2-2026-09-24.md](results/h2-2026-09-24.md) |
| DuckDB | 2026-09-24 | Streamed memory reduced (~7-81MB vs. 344-1076MB buffered) but not flat like the others - matches the documented finding that DuckDB materialises the whole result during execute() before the first fetch; fastest dialect overall (no network) - see [results/duckdb-2026-09-24.md](results/duckdb-2026-09-24.md) |

See `results/` for the full reports.
