"""Tests for SQL2API. Run from the repository root:  python -m unittest discover -s tests -t ."""
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from sql2api import config, create_app, runners, sqltools
from sql2api.errors import ApiError
from sql2api.formats import ResultSetDTO


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

        patcher = mock.patch.dict(os.environ, {'SQL2API_HOME': tmp})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ('SQL2API_API_KEY', 'SQL2API_ALLOW_WRITES', 'SQL2API_MAX_PAGE_SIZE'):
            os.environ.pop(name, None)

        self.client = create_app().test_client()

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
            runners._run_sqlite({'database': self.db_path}, 'DELETE FROM actor', None, 10, 0, True)

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
        outside = (self.connections_file, '../db_connections.json', '/etc/passwd', 'saved_sql/../db_connections.json')
        for path in outside:
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
        self.assertEqual(conns['pg']['password'], config.PASSWORD_MASK)
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
        self.assertEqual(self.client.get('/connections', headers={'X-API-Key': 'k\u00e9y'}).status_code, 401)


class DriverWiringTests(unittest.TestCase):
    """The network runners are covered for real in test_integration.py; these check the driver hand-off."""

    def test_postgres_readonly_session_paginates_and_binds(self):
        cursor = mock.MagicMock()
        cursor.description = [('id',)]
        cursor.fetchall.return_value = [(1,)]
        conn = mock.MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with mock.patch('psycopg2.connect', return_value=conn) as connect:
            columns, rows = runners._run_postgres(
                {'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd', 'db': 'postgres', 'active': True},
                "SELECT id FROM t WHERE n = :n AND s LIKE '%x' LIMIT 500", {'n': 4}, 5, 10, True)
        kwargs = connect.call_args.kwargs
        self.assertEqual((kwargs['dbname'], kwargs['host']), ('d', 'h'))
        self.assertNotIn('active', kwargs)
        self.assertNotIn('db', kwargs)
        conn.set_session.assert_called_once_with(readonly=True)
        cursor.execute.assert_called_once_with("SELECT id FROM t WHERE n = %s AND s LIKE '%%x'\nLIMIT 6 OFFSET 10", [4])
        self.assertEqual((columns, rows), (['id'], [(1,)]))
        conn.close.assert_called_once()

    def test_clickhouse_single_round_trip_and_readonly_setting(self):
        client = mock.MagicMock()
        client.execute.return_value = ([(1,)], [('id', 'UInt8')])
        with mock.patch('clickhouse_driver.Client', return_value=client) as ctor:
            columns, rows = runners._run_clickhouse(
                {'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd', 'db': 'clickhouse'},
                'SELECT id FROM t WHERE id = :id', {'id': 7}, 5, 0, True)
        self.assertNotIn('db', ctor.call_args.kwargs)
        self.assertEqual(client.execute.call_count, 1)  # data and column names come from one round trip
        query, args = client.execute.call_args.args
        self.assertEqual((query, args), ('SELECT id FROM t WHERE id = %(id)s\nLIMIT 6 OFFSET 0', {'id': 7}))
        self.assertEqual(client.execute.call_args.kwargs['settings'], {'readonly': 1})
        self.assertEqual(columns, ['id'])
        client.disconnect.assert_called_once()

    def test_clickhouse_statement_without_result_set(self):
        client = mock.MagicMock()
        client.execute.return_value = []  # what the driver returns for DDL
        with mock.patch('clickhouse_driver.Client', return_value=client):
            self.assertEqual(runners._run_clickhouse({'host': 'h'}, 'CREATE TABLE t (a Int8)', None, 5, 0, False),
                             ([], []))


class ParameterTests(ApiTestCase):
    def test_bound_parameters_accept_any_text_safely(self):
        nasty = "x'; DROP TABLE actor; --"
        res = self.run_sql('SELECT :n AS echo, name FROM actor WHERE actor_id = :id', params={'n': nasty, 'id': 3})
        self.assertEqual(res.get_json(), [{'echo': nasty, 'name': 'Actor 3'}])
        self.assertEqual(len(self.run_sql('SELECT * FROM actor', '?page_size=100').get_json()), 25)

    def test_bound_parameter_validation(self):
        self.assertEqual(self.run_sql('SELECT :a', params={}).status_code, 400)
        self.assertEqual(self.run_sql('SELECT :a', params={'a': [1]}).status_code, 400)
        self.assertEqual(self.run_sql('SELECT 1', params='nope').status_code, 400)

    def test_markers_inside_literals_and_casts_are_ignored(self):
        self.assertEqual(sqltools.named_parameters("SELECT ':a', \":b\", x::int, y, /* :c */ :d -- :e"), ['d'])

    def test_bind_styles(self):
        sql = "SELECT * FROM t WHERE a = :a AND b LIKE '50%' AND c = :a"
        self.assertEqual(sqltools.bind_parameters(sql, {'a': 1}, 'qmark'),
                         ("SELECT * FROM t WHERE a = ? AND b LIKE '50%' AND c = ?", [1, 1]))
        self.assertEqual(sqltools.bind_parameters(sql, {'a': 1}, 'format'),
                         ("SELECT * FROM t WHERE a = %s AND b LIKE '50%%' AND c = %s", [1, 1]))
        self.assertEqual(sqltools.bind_parameters(sql, {'a': 1}, 'pyformat'),
                         ("SELECT * FROM t WHERE a = %(a)s AND b LIKE '50%%' AND c = %(a)s", {'a': 1}))
        # no parameters: statement is untouched so drivers do not apply % formatting to it
        self.assertEqual(sqltools.bind_parameters("SELECT '50%'", {}, 'format'), ("SELECT '50%'", None))

    def test_declared_types_coerce_query_string_values(self):
        declared = {'id': 'int', 'ratio': {'type': 'float'}, 'on': 'bool', 'name': 'str'}
        self.assertEqual(sqltools.coerce_params(declared, {'id': '3', 'ratio': '0.5', 'on': 'yes', 'name': '007',
                                                           'other': '9'}),
                         {'id': 3, 'ratio': 0.5, 'on': True, 'name': '007', 'other': '9'})
        with self.assertRaises(ApiError):
            sqltools.coerce_params(declared, {'id': 'abc'})


class ValueCoercionTests(unittest.TestCase):
    def test_driver_subclasses_become_plain_types_so_yaml_can_dump_them(self):
        class JInt(int):
            pass

        class JDouble(float):
            pass

        class JString(str):
            pass

        dto = ResultSetDTO([(JInt(1), JDouble(2.5), JString('x'), True, None)], ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual([type(v) for v in dto.rows[0]], [int, float, str, bool, type(None)])
        with create_app().test_request_context():
            self.assertIn('a: 1', dto.to_yaml().get_data(as_text=True))


class NamedQueryTests(ApiTestCase):
    def test_get_query_string_params_and_default_connection(self):
        self.save('by_id', sql='SELECT name FROM actor WHERE actor_id = :id',
                  query_parameters={'id': 'int'}, connection_name='lite')
        res = self.client.get('/q/by_id?id=4')
        self.assertEqual(res.get_json(), [{'name': 'Actor 4'}])
        self.assertEqual(self.client.get('/q/by_id?id=abc').status_code, 400)
        self.assertEqual(self.client.get('/q/by_id').status_code, 400)  # id missing
        self.assertEqual(self.client.get('/q/nope?id=1').status_code, 404)
        csv_res = self.client.get('/q/by_id?id=5&format=csv')
        self.assertEqual(csv_res.get_data(as_text=True).splitlines(), ['name', 'Actor 5'])

    def test_post_body_connection_override_and_version_selection(self):
        self.save('v', sql='SELECT 1 AS one')
        self.save('v', sql='SELECT 2 AS two')
        body = {'connection_name': 'lite'}
        self.assertEqual(self.client.post('/q/v', json=body).get_json(), [{'two': 2}])
        self.assertEqual(self.client.post('/q/v?version=1', json=body).get_json(), [{'one': 1}])
        self.assertEqual(self.client.post('/q/v?version=9', json=body).status_code, 404)
        self.assertEqual(self.client.post('/q/v', json={}).status_code, 400)  # no connection anywhere

    def test_legacy_endpoints_still_accept_saved_default_connection(self):
        self.save('d', sql='SELECT 1 AS one', connection_name='lite')
        res = self.client.post('/execute_sql_from_file', json={'filepath': 'd'})
        self.assertEqual(res.get_json(), [{'one': 1}])

    def test_execution_history_is_recorded_and_capped(self):
        self.save('h', sql='SELECT actor_id FROM actor WHERE actor_id = :id', connection_name='lite')
        self.client.get('/q/h?id=1')
        self.client.get('/q/h')  # fails: missing parameter
        with open(os.path.join(self.saved_dir, 'h.json')) as f:
            history = json.load(f)['1']['execution_history']
        self.assertEqual([e['status'] for e in history], ['success', 'error'])
        self.assertEqual(history[0]['rows'], 1)
        self.assertIn('duration_ms', history[0])
        self.assertIn('parameter', history[1]['error'])

        for _ in range(config.HISTORY_LIMIT + 5):
            self.client.get('/q/h?id=1')
        with open(os.path.join(self.saved_dir, 'h.json')) as f:
            self.assertEqual(len(json.load(f)['1']['execution_history']), config.HISTORY_LIMIT)

    def test_delete_versions_and_files(self):
        self.save('x')
        self.save('x')
        self.assertEqual(self.client.delete('/saved_sql/x?version=2').status_code, 200)
        self.assertEqual(self.client.delete('/saved_sql/x?version=2').status_code, 404)
        files = self.client.get('/list_files').get_json()['files']
        self.assertEqual([v['version'] for v in files[0]['versions']], [1])
        self.assertEqual(self.client.delete('/saved_sql/x?version=1').status_code, 200)  # last version -> file gone
        self.assertFalse(os.path.exists(os.path.join(self.saved_dir, 'x.json')))
        self.assertEqual(self.client.delete('/saved_sql/x').status_code, 404)
        self.assertEqual(self.client.delete('/saved_sql/..%2Fdb_connections').status_code, 404)

    def test_delete_connection(self):
        self.assertEqual(self.client.delete('/connections/off').status_code, 200)
        self.assertNotIn('off', self.client.get('/connections').get_json()['connections'])
        self.assertEqual(self.client.delete('/connections/off').status_code, 404)


class PaginationAndFormatTests(ApiTestCase):
    def test_has_more_header_and_page_headers(self):
        res = self.run_sql('SELECT * FROM actor', '?page=2&page_size=10')
        self.assertEqual((res.headers['X-Page'], res.headers['X-Page-Size'], res.headers['X-Has-More']),
                         ('2', '10', 'true'))
        res = self.run_sql('SELECT * FROM actor', '?page=3&page_size=10')
        self.assertEqual(res.headers['X-Has-More'], 'false')
        self.assertEqual(len(res.get_json()), 5)
        res = self.run_sql('SELECT * FROM actor', '?page=1&page_size=25')  # exactly one full page
        self.assertEqual(res.headers['X-Has-More'], 'false')

    def test_ndjson(self):
        res = self.run_sql('SELECT actor_id, name FROM actor ORDER BY actor_id', '?format=ndjson&page_size=2')
        self.assertEqual(res.mimetype, 'application/x-ndjson')
        self.assertEqual([json.loads(line) for line in res.get_data(as_text=True).splitlines()],
                         [{'actor_id': 1, 'name': 'Actor 1'}, {'actor_id': 2, 'name': 'Actor 2'}])


class ConnectionSecretsTests(ApiTestCase):
    def test_env_var_references_are_expanded_for_use_and_left_visible_in_listing(self):
        with open(self.connections_file, 'w') as f:
            json.dump({'connections': {'env': {'db': 'sqlite', 'database': '${IT_DB_PATH}', 'password': '${IT_PW}',
                                               'active': True}}}, f)
        conns = self.client.get('/connections').get_json()['connections']
        self.assertEqual(conns['env']['password'], '${IT_PW}')
        res = self.client.post('/execute_sql', json={'sql': 'SELECT 1 AS one', 'connection_name': 'env'})
        self.assertEqual(res.status_code, 500)  # variable not set
        self.assertIn('IT_DB_PATH', res.get_json()['error'])
        with mock.patch.dict(os.environ, {'IT_DB_PATH': self.db_path, 'IT_PW': 'pw'}):
            res = self.client.post('/execute_sql', json={'sql': 'SELECT 1 AS one', 'connection_name': 'env'})
        self.assertEqual(res.get_json(), [{'one': 1}])


class ServiceEndpointTests(ApiTestCase):
    def test_health_docs_and_openapi_are_public(self):
        os.environ['SQL2API_API_KEY'] = 'k3y'
        self.assertEqual(self.client.get('/health').get_json()['status'], 'ok')
        self.assertEqual(self.client.get('/docs').status_code, 200)
        spec = self.client.get('/openapi.json').get_json()
        self.assertEqual(spec['openapi'], '3.0.3')
        self.assertIn('/q/{name}', spec['paths'])
        self.assertEqual(self.client.get('/connections').status_code, 401)

    def test_root_redirects_to_docs_even_with_an_api_key(self):
        os.environ['SQL2API_API_KEY'] = 'k3y'
        res = self.client.get('/')
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers['Location'].endswith('/docs'))
        self.assertEqual(self.client.get('/favicon.ico').status_code, 204)

    def test_unknown_route_returns_json(self):
        res = self.client.get('/nope')
        self.assertEqual(res.status_code, 404)
        self.assertIn('error', res.get_json())


if __name__ == '__main__':
    unittest.main()
