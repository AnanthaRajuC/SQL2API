"""OpenAPI description of the API, served at /openapi.json and rendered at /docs."""
from . import config

_FORMAT_PARAM = {'name': 'format', 'in': 'query', 'schema': {
    'type': 'string', 'enum': ['json', 'ndjson', 'csv', 'tsv', 'xml', 'yaml', 'xlsx'], 'default': 'json'}}
_PAGE_PARAMS = [
    {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'default': 1}},
    {'name': 'page_size', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'default': 10},
     'description': 'Upper limit is SQL2API_MAX_PAGE_SIZE (default 1000).'},
]
_ROWS = {'description': 'The requested page. Header X-Has-More says whether another page follows.',
         'headers': {'X-Page': {'schema': {'type': 'integer'}}, 'X-Page-Size': {'schema': {'type': 'integer'}},
                     'X-Has-More': {'schema': {'type': 'string', 'enum': ['true', 'false']}}},
         'content': {'application/json': {'schema': {'type': 'array', 'items': {'type': 'object'}}}}}
_ERRORS = {c: {'$ref': '#/components/responses/Error'} for c in ('400', '401', '403', '404', '500')}


def _body(properties, required):
    return {'required': True, 'content': {'application/json': {'schema': {
        'type': 'object', 'required': required, 'properties': properties}}}}


_EXEC_PROPS = {
    'connection_name': {'type': 'string'},
    'format': {'type': 'string'},
    'placeholders': {'type': 'object', 'description': 'Values for :name (bound) and {name} (text) parameters.'},
    'params': {'type': 'object', 'description': 'Alias of placeholders.'},
    'version': {'type': 'integer', 'description': 'Saved version to run (default: latest).'},
}


def build_spec(version):
    saved = {'filepath': {'type': 'string', 'description': 'Saved query name or path inside saved_sql/.'},
             **_EXEC_PROPS}
    return {
        'openapi': '3.0.3',
        'info': {'title': 'SQL2API', 'version': version,
                 'description': 'Run SQL against configured databases and get the results back over HTTP.'},
        'components': {
            'securitySchemes': {'ApiKey': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}},
            'responses': {'Error': {'description': 'Error', 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': {'error': {'type': 'string'}, 'detail': {'type': 'string'}}}}}}},
        },
        'security': [{}, {'ApiKey': []}],
        'paths': {
            '/execute_sql': {'post': {
                'summary': 'Execute SQL', 'tags': ['Query'],
                'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS],
                'requestBody': _body({'sql': {'type': 'string'}, 'connection_name': {'type': 'string'},
                                      'params': {'type': 'object',
                                                 'description': 'Values for :name bound parameters.'}},
                                     ['sql', 'connection_name']),
                'responses': {'200': _ROWS, **_ERRORS}}},
            '/q/{name}': {
                'parameters': [{'name': 'name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                'get': {'summary': 'Run a saved query; extra query-string arguments become parameters',
                        'tags': ['Saved queries'],
                        'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS,
                                       {'name': 'connection_name', 'in': 'query', 'schema': {'type': 'string'}},
                                       {'name': 'version', 'in': 'query', 'schema': {'type': 'integer'}}],
                        'responses': {'200': _ROWS, **_ERRORS}},
                'post': {'summary': 'Run a saved query with a JSON body of parameters', 'tags': ['Saved queries'],
                         'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS],
                         'requestBody': _body(_EXEC_PROPS, []),
                         'responses': {'200': _ROWS, **_ERRORS}}},
            '/execute_sql_from_file': {'post': {
                'summary': 'Run the latest version of a saved query', 'tags': ['Saved queries'],
                'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS],
                'requestBody': _body(saved, ['filepath']), 'responses': {'200': _ROWS, **_ERRORS}}},
            '/execute_sql_with_parameters_from_file': {'post': {
                'summary': 'Run a saved query with parameter values', 'tags': ['Saved queries'],
                'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS],
                'requestBody': _body(saved, ['filepath']), 'responses': {'200': _ROWS, **_ERRORS}}},
            '/save_sql_to_file': {'patch': {
                'summary': 'Save a query (creates the next version)', 'tags': ['Saved queries'],
                'requestBody': _body({
                    'filename': {'type': 'string'}, 'sql_query': {'type': 'string'}, 'author': {'type': 'string'},
                    'description': {'type': 'string'}, 'tags': {'type': 'array', 'items': {'type': 'string'}},
                    'query_parameters': {'type': 'object', 'example': {'actor_id': 'int'}},
                    'connection_name': {'type': 'string', 'description': 'Default connection for /q/{name}.'}},
                    ['filename', 'sql_query', 'author', 'description']),
                'responses': {'200': {'description': 'Saved'}, **_ERRORS}}},
            '/list_files': {'get': {
                'summary': 'List saved queries', 'tags': ['Saved queries'],
                'parameters': [
                    {'name': 'sort_by', 'in': 'query', 'schema': {'type': 'string', 'enum': ['name', 'modified']}},
                    {'name': 'sort_order', 'in': 'query', 'schema': {'type': 'string', 'enum': ['asc', 'desc']}}],
                'responses': {'200': {'description': 'Saved queries with version metadata'}, **_ERRORS}}},
            '/view_file_content': {'get': {
                'summary': 'Raw content of a saved query file', 'tags': ['Saved queries'],
                'parameters': [{'name': 'filename', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}],
                'responses': {'200': {'description': 'File content'}, **_ERRORS}}},
            '/saved_sql/{name}': {'delete': {
                'summary': 'Delete a saved query, or one version with ?version=', 'tags': ['Saved queries'],
                'parameters': [{'name': 'name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                               {'name': 'version', 'in': 'query', 'schema': {'type': 'integer'}}],
                'responses': {'200': {'description': 'Deleted'}, **_ERRORS}}},
            '/connections': {
                'get': {'summary': 'List connections (passwords masked)', 'tags': ['Connections'],
                        'responses': {'200': {'description': 'Connections'}, **_ERRORS}},
                'patch': {'summary': 'Add or update connections', 'tags': ['Connections'],
                          'requestBody': _body({'connections': {
                              'type': 'object', 'description': 'Map of name to connection details.',
                              'additionalProperties': {'type': 'object', 'properties': {
                                  'db': {'type': 'string', 'enum': list(config.SUPPORTED_DB_TYPES)},
                                  'host': {'type': 'string'}, 'port': {'type': 'integer'},
                                  'user': {'type': 'string'}, 'password': {'type': 'string'},
                                  'database': {'type': 'string'}, 'active': {'type': 'boolean'}}}}},
                              ['connections']),
                          'responses': {'200': {'description': 'Updated'}, **_ERRORS}}},
            '/connections/{name}': {'delete': {
                'summary': 'Delete a connection', 'tags': ['Connections'],
                'parameters': [{'name': 'name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                'responses': {'200': {'description': 'Deleted'}, **_ERRORS}}},
            '/health': {'get': {'summary': 'Liveness check', 'tags': ['Service'],
                                'responses': {'200': {'description': 'OK'}}}},
        },
    }


DOCS_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>SQL2API docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: 'openapi.json', dom_id: '#ui'});</script></body></html>
"""
