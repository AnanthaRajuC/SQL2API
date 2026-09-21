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

from sql2api import create_app, runners

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

    def test_saved_query_end_to_end(self):
        self.client.patch('/save_sql_to_file', json={
            'author': 'it', 'description': 'd', 'filename': 'it_query', 'connection_name': 'it',
            'sql_query': 'SELECT name FROM sql2api_it WHERE id = :id', 'query_parameters': {'id': 'int'}})
        res = self.client.get('/q/it_query?id=5')
        self.assertEqual([list(r.values())[0] for r in res.get_json()], ['Item 5'])


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


class MySQLTests(DriverReadOnlyMixin, IntegrationBase, unittest.TestCase):
    db, env_var = 'mysql', 'SQL2API_IT_MYSQL'
    # (SLEEP() and BENCHMARK() are cut short by MySQL's limit but return normally instead of raising an error)
    slow_sql = 'SELECT COUNT(*) FROM ' + ', '.join(f'information_schema.columns c{i}' for i in range(4))


class ClickHouseTests(DriverReadOnlyMixin, IntegrationBase, unittest.TestCase):
    db, env_var = 'clickhouse', 'SQL2API_IT_CLICKHOUSE'
    slow_sql = 'SELECT count() FROM numbers(100000000000)'


class H2Tests(IntegrationBase, unittest.TestCase):
    # H2's JDBC read-only flag is only a hint, so it relies on the SQL guard (covered by test_writes_are_blocked).
    db, env_var = 'h2', 'SQL2API_IT_H2'
    slow_sql = 'SELECT COUNT(*) FROM SYSTEM_RANGE(1, 100000) a, SYSTEM_RANGE(1, 100000) b WHERE (a.x * b.x) % 7 = 3'


if __name__ == '__main__':
    unittest.main()
