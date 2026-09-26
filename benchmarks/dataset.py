"""The synthetic benchmark table: one purpose-built table, not a borrowed schema (TPC-H/TPC-DS benchmark a
query engine's join/aggregation performance, which is not what changed here; this benchmark is about one
thing - how a flat SELECT over N rows of width W behaves buffered vs streamed) - see benchmarks/README.md.

Two independently-controlled knobs, named after their intent rather than a specific byte count so the
target stays clear if the padding math is ever adjusted:

    id       INTEGER, sequential from 1
    payload  a string padded to land close to WIDTHS[width] total bytes for the row

Row content is deterministic (not random), so seeding is fast and a run is reproducible.
"""

WIDTHS = {'narrow': 40, 'wide': 480}  # payload characters; overall row size is a few bytes more than this

CREATE = {
    'mysql': 'CREATE TABLE bench_data (id INT PRIMARY KEY, payload VARCHAR({width}))',
    'postgres': 'CREATE TABLE bench_data (id INT PRIMARY KEY, payload VARCHAR({width}))',
    'clickhouse': 'CREATE TABLE bench_data (id Int32, payload String) ENGINE = MergeTree ORDER BY id',
    'sqlite': 'CREATE TABLE bench_data (id INTEGER PRIMARY KEY, payload TEXT)',
    'h2': 'CREATE TABLE bench_data (id INT PRIMARY KEY, payload VARCHAR({width}))',
    'duckdb': 'CREATE TABLE bench_data (id INTEGER PRIMARY KEY, payload VARCHAR({width}))',
}


def payload(row_id, width):
    """A deterministic string of exactly `width` characters: a readable prefix (so a spot-check of the
    data is meaningful) padded with 'x' to hit the target width precisely."""
    prefix = f'row-{row_id}-'
    return (prefix + 'x' * width)[:width]


def _rows(count, width):
    for i in range(1, count + 1):
        yield i, payload(i, width)


def seed_mysql(conn, count, width):
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS bench_data')
    cur.execute(CREATE['mysql'].format(width=width))
    conn.commit()
    batch = []
    for row in _rows(count, width):
        batch.append(row)
        if len(batch) == 20000:
            cur.executemany('INSERT INTO bench_data VALUES (%s, %s)', batch)
            conn.commit()
            batch.clear()
    if batch:
        cur.executemany('INSERT INTO bench_data VALUES (%s, %s)', batch)
        conn.commit()
    cur.close()


def seed_postgres(conn, count, width):
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS bench_data')
    cur.execute(CREATE['postgres'].format(width=width))
    conn.commit()
    batch = []
    for row in _rows(count, width):
        batch.append(row)
        if len(batch) == 20000:
            cur.executemany('INSERT INTO bench_data VALUES (%s, %s)', batch)
            conn.commit()
            batch.clear()
    if batch:
        cur.executemany('INSERT INTO bench_data VALUES (%s, %s)', batch)
        conn.commit()
    cur.close()


def seed_clickhouse(client, count, width):
    client.execute('DROP TABLE IF EXISTS bench_data')
    client.execute(CREATE['clickhouse'])

    def gen():
        yield from _rows(count, width)

    client.execute('INSERT INTO bench_data VALUES', gen())


def seed_sqlite(conn, count, width):
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS bench_data')
    cur.execute(CREATE['sqlite'])
    batch = []
    for row in _rows(count, width):
        batch.append(row)
        if len(batch) == 20000:
            cur.executemany('INSERT INTO bench_data VALUES (?, ?)', batch)
            batch.clear()
    if batch:
        cur.executemany('INSERT INTO bench_data VALUES (?, ?)', batch)
    conn.commit()
    cur.close()


def seed_h2(conn, count, width):
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS bench_data')
    cur.execute(CREATE['h2'].format(width=width))
    conn.commit()
    batch = []
    for row in _rows(count, width):
        batch.append(row)
        if len(batch) == 20000:
            cur.executemany('INSERT INTO bench_data VALUES (?, ?)', batch)
            conn.commit()
            batch.clear()
    if batch:
        cur.executemany('INSERT INTO bench_data VALUES (?, ?)', batch)
        conn.commit()
    cur.close()


def seed_duckdb(conn, count, width):
    """Unlike every other seeder here, does not build rows in Python and executemany() them in - a single
    20,000-row executemany() batch measured ~20s against DuckDB's Python API (no fast bulk path for
    parameterised row-at-a-time inserts), which would have made seeding alone take ~15 minutes at 1M rows.
    DuckDB is built for set-based bulk generation instead: the same 1M rows via range() + string functions,
    computed entirely inside DuckDB's own engine with no per-row Python marshalling, took ~1.5s - a ~700x
    difference for what is, from the benchmark's perspective, the same data (see payload() above for the
    format this replicates in SQL)."""
    conn.execute('DROP TABLE IF EXISTS bench_data')
    conn.execute(CREATE['duckdb'].format(width=width))
    conn.execute(f"""
        INSERT INTO bench_data
        SELECT i, substr('row-' || i || '-' || repeat('x', {width}), 1, {width})
        FROM range(1, {count + 1}) AS r(i)
    """)


SEEDERS = {
    'mysql': seed_mysql,
    'postgres': seed_postgres,
    'clickhouse': seed_clickhouse,
    'sqlite': seed_sqlite,
    'h2': seed_h2,
    'duckdb': seed_duckdb,
}
