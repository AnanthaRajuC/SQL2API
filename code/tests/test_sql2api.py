"""Tests for SQL2API. Run from the code/ folder:  python -m unittest discover -s tests -t ."""
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import SQL2API


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = self.tmp.name

        self.db_path = os.path.join(tmp, 'test.db')
        conn = sqlite3.connect(self.db_path)
        conn.execute('CREATE TABLE actor (actor_id INTEGER, name TEXT, born TEXT)')
        conn.executemany('INSERT INTO actor VALUES (?, ?, ?)',
                         [(i, f'Actor {i}', f'19{i:02d}-01-01') for i in range(1, 26)])
        conn.commit()
        conn.close()

        self.saved_dir = os.path.join(tmp, 'saved_sql')
        self.connections_file = os.path.join(tmp, 'db_connections.json')
        with open(self.connections_file, 'w') as f:
            json.dump({'connections': {
                'lite': {'db': 'sqlite', 'database': self.db_path, 'active': True},
                'off': {'db': 'sqlite', 'database': self.db_path, 'active': False},
                'pg': {'db': 'postgres', 'host': 'h', 'user': 'u', 'password': 'secret', 'database': 'd',
                       'active': True},
            }}, f)

        patches = [
            mock.patch.object(SQL2API, 'BASE_DIR', tmp),
            mock.patch.object(SQL2API, 'SAVED_SQL_DIR', self.saved_dir),
            mock.patch.object(SQL2API, 'CONNECTIONS_FILE', self.connections_file),
            mock.patch.dict(os.environ, {}, clear=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop('SQL2API_API_KEY', None)
        os.environ.pop('SQL2API_ALLOW_WRITES', None)

        self.client = SQL2API.app.test_client()

    def run_sql(self, sql, query='', **body):
        return self.client.post(f'/execute_sql{query}', json={'sql': sql, 'connection_name': 'lite', **body})

    def save(self, filename='q', sql='SELECT * FROM actor ORDER BY actor_id', **extra):
        return self.client.patch('/save_sql_to_file', json={
            'author': 'a', 'description': 'd', 'sql_query': sql, 'filename': filename, **extra})


class ExecuteSqlTests(ApiTestCase):
    def test_json_default_and_pagination(self):
        res = self.run_sql('SELECT * FROM actor ORDER BY actor_id')
        rows = res.get_json()
        self.assertEqual(len(rows), 10)
        self.assertEqual(list(rows[0]), ['actor_id', 'name', 'born'])  # column order preserved
        self.assertEqual(rows[0]['name'], 'Actor 1')

        rows = self.run_sql('SELECT * FROM actor ORDER BY actor_id', '?page=3&page_size=10').get_json()
        self.assertEqual([r['actor_id'] for r in rows], [21, 22, 23, 24, 25])

    def test_existing_limit_is_replaced_by_pagination(self):
        rows = self.run_sql('SELECT actor_id FROM actor ORDER BY actor_id LIMIT 2;', '?page_size=4').get_json()
        self.assertEqual(len(rows), 4)
        rows = self.run_sql('select actor_id from actor order by actor_id limit 3 offset 1',
                            '?page_size=4').get_json()
        self.assertEqual(len(rows), 4)

    def test_trailing_line_comment_does_not_swallow_limit(self):
        rows = self.run_sql('SELECT actor_id FROM actor -- everything', '?page_size=3').get_json()
        self.assertEqual(len(rows), 3)

    def test_formats(self):
        csv_res = self.run_sql('SELECT actor_id, name FROM actor ORDER BY actor_id', '?format=csv&page_size=2')
        self.assertEqual(csv_res.mimetype, 'text/csv')
        self.assertEqual(csv_res.get_data(as_text=True).splitlines(), ['actor_id,name', '1,Actor 1', '2,Actor 2'])

        tsv_res = self.run_sql('SELECT actor_id, name FROM actor ORDER BY actor_id', '?format=tsv&page_size=1')
        self.assertEqual(tsv_res.get_data(as_text=True).splitlines(), ['actor_id\tname', '1\tActor 1'])

        xml_res = self.run_sql('SELECT actor_id, name FROM actor ORDER BY actor_id', '?format=xml&page_size=1')
        self.assertEqual(xml_res.get_data(as_text=True),
                         '<data><item><actor_id>1</actor_id><name>Actor 1</name></item></data>')

        yaml_res = self.run_sql('SELECT actor_id, name FROM actor ORDER BY actor_id', '?format=yaml&page_size=1')
        self.assertEqual(yaml_res.get_data(as_text=True), '- actor_id: 1\n  name: Actor 1\n')

        xlsx_res = self.run_sql('SELECT actor_id FROM actor', '?format=xlsx')
        self.assertTrue(xlsx_res.get_data().startswith(b'PK'))
        self.assertIn('result.xlsx', xlsx_res.headers['Content-Disposition'])

    def test_format_from_body_and_bad_format(self):
        res = self.run_sql('SELECT actor_id FROM actor', format='csv')
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertEqual(self.run_sql('SELECT 1', '?format=pdf').status_code, 400)

    def test_xml_sanitises_column_names_and_duplicate_columns_are_kept(self):
        res = self.run_sql('SELECT actor_id AS "1 id", actor_id, actor_id FROM actor', '?format=json&page_size=1')
        self.assertEqual(res.get_json(), [{'1 id': 1, 'actor_id': 1, 'actor_id_2': 1}])
        xml = self.run_sql('SELECT actor_id AS "1 id" FROM actor', '?format=xml&page_size=1')
        self.assertEqual(xml.get_data(as_text=True), '<data><item><_1_id>1</_1_id></item></data>')

    def test_empty_result(self):
        res = self.run_sql('SELECT * FROM actor WHERE actor_id < 0')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {'message': 'No results returned'})

    def test_non_select_statements_are_paged_without_limit_rewriting(self):
        # EXPLAIN can't take a LIMIT clause, so it is fetched whole and sliced instead
        res = self.run_sql('EXPLAIN QUERY PLAN SELECT * FROM actor', '?page_size=5')
        self.assertEqual(res.status_code, 200)

    def test_validation_errors(self):
        self.assertEqual(self.client.post('/execute_sql', json={'connection_name': 'lite'}).status_code, 400)
        self.assertEqual(self.client.post('/execute_sql', json={'sql': 'SELECT 1'}).status_code, 400)
        self.assertEqual(self.client.post('/execute_sql', data='nope').status_code, 400)
        for query in ('?page=abc', '?page=0', '?page_size=-1', '?page_size=100000'):
            self.assertEqual(self.run_sql('SELECT 1', query).status_code, 400, query)

    def test_connection_errors(self):
        res = self.client.post('/execute_sql', json={'sql': 'SELECT 1', 'connection_name': 'nope'})
        self.assertEqual(res.status_code, 404)
        res = self.client.post('/execute_sql', json={'sql': 'SELECT 1', 'connection_name': 'off'})
        self.assertEqual(res.status_code, 403)

    def test_bad_sql_returns_500_with_detail(self):
        res = self.run_sql('SELECT * FROM missing_table')
        self.assertEqual(res.status_code, 500)
        self.assertIn('missing_table', res.get_json()['detail'])


class ReadOnlyTests(ApiTestCase):
    def test_writes_and_multiple_statements_are_rejected(self):
        expected = {
            'DELETE FROM actor': 403,
            'DROP TABLE actor': 403,
            "INSERT INTO actor VALUES (99, 'x', 'y')": 403,
            '/* hi */ UPDATE actor SET name = "x"': 403,
            'SELECT 1 /*! DROP TABLE actor */': 403,
            'SELECT 1; DELETE FROM actor': 400,
        }
        for sql, status in expected.items():
            self.assertEqual(self.run_sql(sql).status_code, status, sql)
        self.assertEqual(len(self.run_sql('SELECT * FROM actor', '?page_size=100').get_json()), 25)

    def test_semicolon_inside_literal_is_fine(self):
        res = self.run_sql("SELECT ';' AS semi FROM actor", '?page_size=1')
        self.assertEqual(res.get_json(), [{'semi': ';'}])

    def test_sqlite_connection_is_read_only_at_driver_level(self):
        with self.assertRaises(sqlite3.OperationalError):
            SQL2API._run_sqlite({'database': self.db_path}, 'DELETE FROM actor', 10, 0, True)

    def test_writes_can_be_enabled(self):
        os.environ['SQL2API_ALLOW_WRITES'] = '1'
        res = self.run_sql("INSERT INTO actor VALUES (99, 'New', '2000-01-01')")
        self.assertEqual(res.get_json(), {'message': 'No results returned'})
        rows = self.run_sql('SELECT name FROM actor WHERE actor_id = 99').get_json()
        self.assertEqual(rows, [{'name': 'New'}])


class SavedQueryTests(ApiTestCase):
    def test_save_versions_and_list(self):
        first = self.save('my query')
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()['uuid'])
        self.save('my query', sql='SELECT 2', tags=['x'])
        self.save('another')

        with open(os.path.join(self.saved_dir, 'my query.json')) as f:
            saved = json.load(f)
        self.assertEqual(sorted(saved), ['1', '2'])
        self.assertEqual(saved['2']['version'], 2)
        self.assertEqual(saved['2']['tags'], ['x'])

        files = self.client.get('/list_files').get_json()['files']
        self.assertEqual([f['filename'] for f in files], ['another', 'my query'])
        self.assertEqual([v['version'] for v in files[1]['versions']], [1, 2])

        files = self.client.get('/list_files?sort_by=name&sort_order=desc').get_json()['files']
        self.assertEqual([f['filename'] for f in files], ['my query', 'another'])
        self.assertEqual(self.client.get('/list_files?sort_by=size').status_code, 400)

    def test_save_validation(self):
        self.assertEqual(self.client.patch('/save_sql_to_file', json={'author': 'a'}).status_code, 400)
        for name in ('../evil', 'a/b', '.hidden', ''):
            self.assertEqual(self.save(name).status_code, 400, name)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'evil.json')))

    def test_execute_latest_version_from_file(self):
        self.save('q', sql='SELECT actor_id FROM actor ORDER BY actor_id')
        self.save('q', sql='SELECT name FROM actor ORDER BY actor_id')
        for filepath in ('q', 'q.json', 'saved_sql/q.json', os.path.join(self.saved_dir, 'q.json')):
            res = self.client.post('/execute_sql_from_file?page_size=2',
                                   json={'filepath': filepath, 'connection_name': 'lite', 'format': 'csv'})
            self.assertEqual(res.get_data(as_text=True).splitlines(), ['name', 'Actor 1', 'Actor 2'], filepath)

    def test_parameters(self):
        self.save('p', sql="SELECT name FROM actor WHERE actor_id = {id} AND born LIKE '{year}%'")
        ok = self.client.post('/execute_sql_with_parameters_from_file', json={
            'filepath': 'p', 'connection_name': 'lite', 'placeholders': {'id': 3, 'year': '1903'}})
        self.assertEqual(ok.get_json(), [{'name': 'Actor 3'}])

        for bad in ({'id': '1 OR 1=1; --', 'year': '1903'}, {'id': 3, 'year': "x' OR '1'='1"},
                    {'id': '3 -- ', 'year': 'x'}, {'id': [1], 'year': 'x'}):
            res = self.client.post('/execute_sql_with_parameters_from_file', json={
                'filepath': 'p', 'connection_name': 'lite', 'placeholders': bad})
            self.assertEqual(res.status_code, 400, bad)

        missing = self.client.post('/execute_sql_with_parameters_from_file', json={
            'filepath': 'p', 'connection_name': 'lite', 'placeholders': {'id': 3}})
        self.assertEqual(missing.status_code, 400)
        self.assertIn('year', missing.get_json()['error'])

    def test_file_access_is_confined_to_saved_sql(self):
        self.save('q')
        for path in (self.connections_file, '../db_connections.json', '/etc/passwd', 'saved_sql/../db_connections.json'):
            res = self.client.get('/view_file_content', query_string={'filename': path})
            self.assertIn(res.status_code, (403, 404), path)
            self.assertNotIn('password', res.get_data(as_text=True))
            res = self.client.post('/execute_sql_from_file',
                                   json={'filepath': path, 'connection_name': 'lite'})
            self.assertIn(res.status_code, (403, 404), path)

        ok = self.client.get('/view_file_content', query_string={'filename': 'q'})
        self.assertEqual(ok.status_code, 200)
        self.assertIn('SELECT', ok.get_json()['content'])
        self.assertEqual(self.client.get('/view_file_content').status_code, 400)
        self.assertEqual(self.client.get('/view_file_content?filename=nope').status_code, 404)


class ConnectionTests(ApiTestCase):
    def test_get_masks_passwords(self):
        conns = self.client.get('/connections').get_json()['connections']
        self.assertEqual(conns['pg']['password'], SQL2API.PASSWORD_MASK)
        self.assertNotIn('secret', json.dumps(conns))

    def test_patch_keeps_masked_password_and_validates(self):
        conns = self.client.get('/connections').get_json()['connections']
        conns['pg']['host'] = 'new-host'
        conns['fresh'] = {'db': 'sqlite', 'database': 'x.db', 'active': True}
        self.assertEqual(self.client.patch('/connections', json={'connections': conns}).status_code, 200)

        with open(self.connections_file) as f:
            stored = json.load(f)['connections']
        self.assertEqual(stored['pg']['password'], 'secret')
        self.assertEqual(stored['pg']['host'], 'new-host')
        self.assertIn('fresh', stored)

        for bad in ({}, {'connections': {}}, {'connections': {'x': {'db': 'oracle'}}},
                    {'connections': {'x': 'nope'}}):
            self.assertEqual(self.client.patch('/connections', json=bad).status_code, 400, bad)


class ApiKeyTests(ApiTestCase):
    def test_api_key_is_enforced_only_when_configured(self):
        self.assertEqual(self.client.get('/connections').status_code, 200)
        os.environ['SQL2API_API_KEY'] = 'k3y'
        self.assertEqual(self.client.get('/connections').status_code, 401)
        self.assertEqual(self.client.get('/connections', headers={'X-API-Key': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.get('/connections', headers={'X-API-Key': 'k3y'}).status_code, 200)


class DriverWiringTests(unittest.TestCase):
    """The network databases can't run here, so check the SQL and options each runner hands its driver."""

    def test_postgres_uses_readonly_session_and_paginates(self):
        cursor = mock.MagicMock()
        cursor.description = [('id',)]
        cursor.fetchall.return_value = [(1,)]
        conn = mock.MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with mock.patch('psycopg2.connect', return_value=conn) as connect:
            columns, rows = SQL2API._run_postgres(
                {'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd', 'db': 'postgres', 'active': True},
                'SELECT id FROM t LIMIT 500', 5, 10, True)
        kwargs = connect.call_args.kwargs
        self.assertEqual((kwargs['dbname'], kwargs['host']), ('d', 'h'))
        self.assertNotIn('active', kwargs)
        self.assertNotIn('db', kwargs)
        conn.set_session.assert_called_once_with(readonly=True)
        cursor.execute.assert_called_once_with('SELECT id FROM t\nLIMIT 5 OFFSET 10')
        self.assertEqual((columns, rows), (['id'], [(1,)]))
        conn.close.assert_called_once()

    def test_clickhouse_readonly_setting(self):
        client = mock.MagicMock()
        client.execute.return_value = ([(1,)], [('id', 'UInt8')])
        with mock.patch('clickhouse_driver.Client', return_value=client) as ctor:
            columns, rows = SQL2API._run_clickhouse(
                {'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd', 'db': 'clickhouse'},
                'SELECT id FROM t', 5, 0, True)
        self.assertNotIn('db', ctor.call_args.kwargs)
        self.assertEqual(client.execute.call_count, 1)  # data and column names come from one round trip
        self.assertEqual(client.execute.call_args.kwargs['settings'], {'readonly': 1})
        self.assertEqual(columns, ['id'])
        client.disconnect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
