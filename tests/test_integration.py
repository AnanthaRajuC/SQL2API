"""Integration tests against real database servers.

Each database is opt-in: set the matching variable to a JSON connection object, e.g.

    SQL2API_IT_POSTGRES='{"host": "localhost", "user": "postgres", "password": "pw", "database": "postgres"}'
    SQL2API_IT_MYSQL=...       SQL2API_IT_CLICKHOUSE=...       SQL2API_IT_H2=...

The tests create and drop a table called sql2api_it, so point them at a scratch database.
CI provides these as service containers (see .github/workflows/ci.yml).
"""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from sql2api import create_app, pool, runners

CREATE = {
    'postgres': 'CREATE TABLE sql2api_it (id INT, name VARCHAR(50), price NUMERIC(8, 2), added TIMESTAMP)',
    'mysql': 'CREATE TABLE sql2api_it (id INT, name VARCHAR(50), price DECIMAL(8, 2), added DATETIME)',
    'h2': 'CREATE TABLE sql2api_it (id INT, name VARCHAR(50), price DECIMAL(8, 2), added TIMESTAMP)',
    'clickhouse': 'CREATE TABLE sql2api_it (id Int32, name String, price Decimal(8, 2), added DateTime) '
                  'ENGINE = MergeTree ORDER BY id',
}
INSERT = {
    'postgres': "INSERT INTO sql2api_it VALUES ({i}, 'Item {i}', {i}.50, '2024-01-{i:02d} 10:00:00')",
    'mysql': "INSERT INTO sql2api_it VALUES ({i}, 'Item {i}', {i}.50, '2024-01-{i:02d} 10:00:00')",
    'h2': "INSERT INTO sql2api_it VALUES ({i}, 'Item {i}', {i}.50, TIMESTAMP '2024-01-{i:02d} 10:00:00')",
    'clickhouse': "INSERT INTO sql2api_it VALUES ({i}, 'Item {i}', {i}.50, '2024-01-{i:02d} 10:00:00')",
}


class IntegrationBase:
    db = None  # set by subclasses
    env_var = None
    slow_sql = None  # a statement that would run for minutes
    finite_slow_sql = None  # a statement that takes about two seconds
    connection_id_sql = None  # returns an id that identifies the database connection serving it

    @classmethod
    def setUpClass(cls):
        raw = os.environ.get(cls.env_var)
        if not raw:
            raise unittest.SkipTest(f'{cls.env_var} not set')
        cls.details = {**json.loads(raw), 'db': cls.db, 'active': True}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with open(os.path.join(self.tmp.name, 'db_connections.json'), 'w') as f:
            json.dump({'connections': {'it': self.details}}, f)
        patcher = mock.patch.dict(os.environ, {'SQL2API_HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('SQL2API_API_KEY', None)
        self.client = create_app().test_client()

        # Setting up and tearing down needs writes; the tests themselves run read-only.
        with mock.patch.dict(os.environ, {'SQL2API_ALLOW_WRITES': '1'}):
            self.write('DROP TABLE IF EXISTS sql2api_it')
            self.write(CREATE[self.db])
            for i in range(1, 8):
                self.write(INSERT[self.db].format(i=i))
        self.addCleanup(self.drop)

    def write(self, sql):
        res = self.client.post('/execute_sql', json={'sql': sql, 'connection_name': 'it'})
        self.assertLess(res.status_code, 300, res.get_data(as_text=True))

    def drop(self):
        with mock.patch.dict(os.environ, {'SQL2API_ALLOW_WRITES': '1'}):
            self.client.post('/execute_sql', json={'sql': 'DROP TABLE IF EXISTS sql2api_it',
                                                   'connection_name': 'it'})

    def query(self, sql, query='', **body):
        return self.client.post(f'/execute_sql{query}', json={'sql': sql, 'connection_name': 'it', **body})

    # ---- tests ----------------------------------------------------------------------

    def test_pagination_and_has_more(self):
        res = self.query('SELECT id FROM sql2api_it ORDER BY id', '?page=2&page_size=3')
        self.assertEqual([r[list(r)[0]] for r in res.get_json()], [4, 5, 6])
        self.assertEqual(res.headers['X-Has-More'], 'true')
        res = self.query('SELECT id FROM sql2api_it ORDER BY id LIMIT 100', '?page=3&page_size=3')
        self.assertEqual(len(res.get_json()), 1)
        self.assertEqual(res.headers['X-Has-More'], 'false')

    def test_types_serialise(self):
        row = self.query('SELECT * FROM sql2api_it WHERE id = 2').get_json()[0]
        values = {k.lower(): v for k, v in row.items()}
        self.assertEqual(values['id'], 2)
        self.assertEqual(values['name'], 'Item 2')
        self.assertEqual(float(values['price']), 2.5)
        self.assertEqual(values['added'], '2024-01-02 10:00:00')

    def test_bound_parameters(self):
        nasty = "Item 3'; DROP TABLE sql2api_it; --"
        res = self.query('SELECT id FROM sql2api_it WHERE id = :id OR name = :name',
                         params={'id': 3, 'name': nasty})
        self.assertEqual([list(r.values())[0] for r in res.get_json()], [3])
        # a literal % in the SQL must survive drivers that use %-style parameters
        res = self.query("SELECT id FROM sql2api_it WHERE name LIKE 'Item%' AND id = :id", params={'id': 1})
        self.assertEqual(len(res.get_json()), 1)
        self.assertEqual(len(self.query('SELECT * FROM sql2api_it', '?page_size=100').get_json()), 7)

    def test_all_formats(self):
        for fmt in ('json', 'ndjson', 'csv', 'tsv', 'xml', 'yaml', 'xlsx'):
            res = self.query('SELECT * FROM sql2api_it ORDER BY id', f'?format={fmt}&page_size=2')
            self.assertEqual(res.status_code, 200, fmt)
            self.assertTrue(res.get_data(), fmt)

    def test_writes_are_blocked(self):
        res = self.query('DELETE FROM sql2api_it')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(len(self.query('SELECT * FROM sql2api_it', '?page_size=100').get_json()), 7)

    def test_query_timeout_cancels_the_statement_and_keeps_the_service_usable(self):
        started = time.monotonic()
        res = self.query(self.slow_sql, '?timeout=1')
        elapsed = time.monotonic() - started
        self.assertEqual(res.status_code, 504, res.get_data(as_text=True))
        self.assertLess(elapsed, 10, 'the statement should be cancelled close to the 1 second limit')
        self.assertIn('time limit', res.get_json()['error'])
        self.assertEqual(len(self.query('SELECT * FROM sql2api_it', '?page_size=100').get_json()), 7)

    # ---- connection pooling ----------------------------------------------------------

    def connection_ids(self, count):
        return [list(self.query(self.connection_id_sql).get_json()[0].values())[0] for _ in range(count)]

    def test_connections_are_reused_when_pooled(self):
        if not self.connection_id_sql:
            self.skipTest('no connection id query for this database')
        self.assertEqual(len(set(self.connection_ids(4))), 1)

    def test_every_request_gets_its_own_connection_when_pooling_is_disabled(self):
        if not self.connection_id_sql:
            self.skipTest('no connection id query for this database')
        with mock.patch.dict(os.environ, {'SQL2API_POOL_SIZE': '0'}):
            self.assertEqual(len(set(self.connection_ids(3))), 3)

    def test_pooled_connection_sees_data_committed_elsewhere(self):
        before = self.query('SELECT COUNT(*) AS n FROM sql2api_it').get_json()[0]
        before = list(before.values())[0]
        # a separate, unpooled connection inserts and commits
        runners.RUNNERS[self.db](self.details, INSERT[self.db].format(i=8), None, 10, 0, False, None, None)
        after = list(self.query('SELECT COUNT(*) AS n FROM sql2api_it').get_json()[0].values())[0]
        self.assertEqual((int(before), int(after)), (7, 8))

    def test_a_request_limit_does_not_leak_to_the_next_user_of_the_connection(self):
        if not self.finite_slow_sql:
            self.skipTest('no two-second statement for this database')
        self.assertEqual(self.query('SELECT 1 AS one', '?timeout=1').status_code, 200)  # leaves a 1s limit behind?
        started = time.monotonic()
        res = self.query(self.finite_slow_sql)  # server default limit (30s) must apply again
        self.assertEqual(res.status_code, 200, res.get_data(as_text=True))
        self.assertGreater(time.monotonic() - started, 1.5, 'the previous request\'s 1 second limit cut this one short')

    def test_read_only_mode_holds_on_a_reused_connection(self):
        shared = pool.get_pool()
        self.assertIsNotNone(shared)
        run = runners.RUNNERS[self.db]
        run(self.details, 'SELECT * FROM sql2api_it', None, 10, 0, True, 5, shared)  # warms the pool
        if self.db != 'h2':  # H2 relies on the SQL guard instead (see H2Tests)
            with self.assertRaises(Exception):  # noqa: B017 - each driver raises its own error type
                run(self.details, 'DELETE FROM sql2api_it', None, 10, 0, True, 5, shared)
        self.assertEqual(len(self.query('SELECT * FROM sql2api_it', '?page_size=100').get_json()), 7)

    def test_concurrent_requests_all_succeed(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda i: self.query('SELECT id FROM sql2api_it ORDER BY id',
                                                             '?page_size=3').status_code, range(30)))
        self.assertEqual(set(results), {200})

    def test_saved_query_end_to_end(self):
        self.client.patch('/save_sql_to_file', json={
            'author': 'it', 'description': 'd', 'filename': 'it_query', 'connection_name': 'it',
            'sql_query': 'SELECT name FROM sql2api_it WHERE id = :id', 'query_parameters': {'id': 'int'}})
        res = self.client.get('/q/it_query?id=5')
        self.assertEqual([list(r.values())[0] for r in res.get_json()], ['Item 5'])

    def test_schema_lists_the_table_and_its_columns(self):
        res = self.client.get('/connections/it/schema')
        self.assertEqual(res.status_code, 200, res.get_data(as_text=True))
        tables = {t['name'].lower(): t for t in res.get_json()['tables']}
        self.assertIn('sql2api_it', tables)
        self.assertEqual(tables['sql2api_it']['type'], 'table')
        columns = {c['name'].lower() for c in tables['sql2api_it']['columns']}
        self.assertEqual(columns, {'id', 'name', 'price', 'added'})


class DriverReadOnlyMixin:
    """Databases whose driver enforces read-only sessions should refuse writes even if the SQL guard is bypassed."""

    def test_driver_level_readonly(self):
        with self.assertRaises(Exception):  # noqa: B017 - each driver raises its own error type
            runners.RUNNERS[self.db](self.details, 'DELETE FROM sql2api_it', None, 10, 0, True)
        rows = self.query('SELECT * FROM sql2api_it', '?page_size=100').get_json()
        self.assertEqual(len(rows), 7)


class PostgresTests(DriverReadOnlyMixin, IntegrationBase, unittest.TestCase):
    db, env_var = 'postgres', 'SQL2API_IT_POSTGRES'
    slow_sql = 'SELECT pg_sleep(60)'
    finite_slow_sql = 'SELECT pg_sleep(2)'
    connection_id_sql = 'SELECT pg_backend_pid() AS id'


class MySQLTests(DriverReadOnlyMixin, IntegrationBase, unittest.TestCase):
    db, env_var = 'mysql', 'SQL2API_IT_MYSQL'
    finite_slow_sql = 'SELECT SLEEP(2) AS s'
    connection_id_sql = 'SELECT CONNECTION_ID() AS id'
    # (SLEEP() and BENCHMARK() are cut short by MySQL's limit but return normally instead of raising an error)
    slow_sql = 'SELECT COUNT(*) FROM ' + ', '.join(f'information_schema.columns c{i}' for i in range(4))


class ClickHouseTests(DriverReadOnlyMixin, IntegrationBase, unittest.TestCase):
    db, env_var = 'clickhouse', 'SQL2API_IT_CLICKHOUSE'
    slow_sql = 'SELECT count() FROM numbers(100000000000)'
    finite_slow_sql = 'SELECT sleep(2) AS s'


class H2Tests(IntegrationBase, unittest.TestCase):
    # H2's JDBC read-only flag is only a hint, so it relies on the SQL guard (covered by test_writes_are_blocked).
    db, env_var = 'h2', 'SQL2API_IT_H2'
    slow_sql = 'SELECT COUNT(*) FROM SYSTEM_RANGE(1, 100000) a, SYSTEM_RANGE(1, 100000) b WHERE (a.x * b.x) % 7 = 3'
    connection_id_sql = 'SELECT SESSION_ID() AS id'


if __name__ == '__main__':
    unittest.main()
