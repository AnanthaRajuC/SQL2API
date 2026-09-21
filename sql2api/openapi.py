"""OpenAPI description of the API, served at /openapi.json and rendered at /docs."""
import re
from urllib.parse import quote

from . import config
from .params import json_schema

_FORMAT_PARAM = {'name': 'format', 'in': 'query', 'schema': {
    'type': 'string', 'enum': ['json', 'ndjson', 'csv', 'tsv', 'xml', 'yaml', 'xlsx'], 'default': 'json'}}
_PAGE_PARAMS = [
    {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'default': 1}},
    {'name': 'page_size', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'default': 10},
     'description': 'Upper limit is SQL2API_MAX_PAGE_SIZE (default 1000).'},
    {'name': 'timeout', 'in': 'query', 'schema': {'type': 'number', 'minimum': 0, 'exclusiveMinimum': True},
     'description': 'Seconds the query may run before it is cancelled (504). Can lower, never raise, the server '
                    'limit SQL2API_QUERY_TIMEOUT (default 30; 0 disables the server limit).'},
]
_ROWS = {'description': 'The requested page. Header X-Has-More says whether another page follows.',
         'headers': {'X-Page': {'schema': {'type': 'integer'}}, 'X-Page-Size': {'schema': {'type': 'integer'}},
                     'X-Has-More': {'schema': {'type': 'string', 'enum': ['true', 'false']}}},
         'content': {'application/json': {'schema': {'type': 'array', 'items': {'type': 'object'}}}}}
_ERRORS = {c: {'$ref': '#/components/responses/Error'} for c in ('400', '401', '403', '404', '429', '500', '504')}


def _object_schema(properties, required=()):
    """An object schema; OpenAPI 3.0 forbids an empty ``required`` list, so it is only included when non-empty."""
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = list(required)
    return schema


def _body(properties, required):
    return {'required': True, 'content': {'application/json': {'schema': _object_schema(properties, required)}}}


_EXEC_PROPS = {
    'connection_name': {'type': 'string'},
    'format': {'type': 'string'},
    'placeholders': {'type': 'object', 'description': 'Values for :name (bound) and {name} (text) parameters.'},
    'params': {'type': 'object', 'description': 'Alias of placeholders.'},
    'version': {'type': 'integer', 'description': 'Saved version to run (default: latest).'},
}


def _saved_query_paths(queries):
    """One documented endpoint per saved query, with its declared parameters and rules."""
    paths, seen = {}, set()
    for query in queries:
        name = query['name']
        has_default_connection = bool(query.get('connection_name'))
        properties, required, query_params = {}, [], []
        for param, spec in query['parameters'].items():
            schema = json_schema(spec)
            entry = {'name': param, 'in': 'query', 'required': spec['required'], 'schema': schema}
            if spec['description']:
                entry['description'] = spec['description']
            query_params.append(entry)
            properties[param] = {**schema, **({'description': spec['description']} if spec['description'] else {})}
            if spec['required']:
                required.append(param)
        connection = {'name': 'connection_name', 'in': 'query', 'required': not has_default_connection,
                      'schema': {'type': 'string', **({'default': query['connection_name']}
                                                      if has_default_connection else {})}}
        common = [connection, {'name': 'version', 'in': 'query', 'schema': {'type': 'integer'},
                               'description': f"Saved version to run (default: latest, currently {query['version']})."},
                  _FORMAT_PARAM, *_PAGE_PARAMS]
        summary = query.get('description') or f'Run the saved query {name}'
        tags = query.get('tags')
        detail = f"Runs version {query['version']} of the saved query '{name}'."
        if tags:
            detail += ' Tags: ' + (tags if isinstance(tags, str) else ', '.join(map(str, tags))) + '.'
        operation_id = 'run_' + re.sub(r'\W', '_', name)
        while operation_id in seen:
            operation_id += '_'
        seen.add(operation_id)
        body_properties = {'params': _object_schema(properties, required),
                           'connection_name': connection['schema'], 'version': {'type': 'integer'},
                           'format': {'type': 'string'}, 'timeout': {'type': 'number'}}
        paths['/q/' + quote(name, safe='')] = {
            'get': {'summary': summary, 'description': detail, 'tags': ['Saved queries (live)'],
                    'operationId': operation_id, 'parameters': [*query_params, *common],
                    'responses': {'200': _ROWS, **_ERRORS}},
            'post': {'summary': summary + ' (parameters in a JSON body)', 'description': detail,
                     'tags': ['Saved queries (live)'], 'operationId': operation_id + '_post',
                     'parameters': [_FORMAT_PARAM, *_PAGE_PARAMS],
                     'requestBody': {'required': bool(required), 'content': {'application/json': {
                         'schema': _object_schema(body_properties)}}},
                     'responses': {'200': _ROWS, **_ERRORS}},
        }
    return paths


def build_spec(version, saved_queries=None):
    saved = {'filepath': {'type': 'string', 'description': 'Saved query name or path inside saved_sql/.'},
             **_EXEC_PROPS}
    spec = {
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
    if saved_queries:
        spec['paths'].update(_saved_query_paths(saved_queries))
        spec['tags'] = [{'name': 'Saved queries (live)',
                         'description': 'One endpoint per saved query, generated from its latest version: its '
                                        'declared parameters and their rules, and its default connection.'}]
    return spec


DOCS_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>SQL2API docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<style>
  body { margin: 0; font-family: sans-serif; }
  #key-bar { padding: 8px 16px; background: #f4f4f4; border-bottom: 1px solid #ddd; font-size: 14px; }
  #key-bar input { width: 260px; padding: 4px; }
</style></head>
<body>
<div id="key-bar">
  API key (only needed if the server sets SQL2API_API_KEY; it reveals your saved queries below and is
  sent with "Try it out" requests; kept for this browser tab only):
  <input id="key" type="password" autocomplete="off" placeholder="X-API-Key">
  <button id="save-key">Apply</button>
</div>
<div id="ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  var stored = '';
  try { stored = sessionStorage.getItem('sql2api-key') || ''; } catch (e) {}
  document.getElementById('key').value = stored;
  document.getElementById('save-key').onclick = function () {
    try { sessionStorage.setItem('sql2api-key', document.getElementById('key').value); } catch (e) {}
    location.reload();
  };
  SwaggerUIBundle({
    url: 'openapi.json', dom_id: '#ui',
    requestInterceptor: function (req) { if (stored) { req.headers['X-API-Key'] = stored; } return req; }
  });
</script></body></html>
"""
