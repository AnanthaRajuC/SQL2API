"""The Flask application: HTTP routes on top of the store, engine and formatters."""
import hmac
import logging
import math

from flask import Blueprint, Flask, Response, jsonify, redirect, request, url_for
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from . import config, engine, openapi, sqltools, store
from .errors import ApiError
from .formats import FORMATTERS, json_default

log = logging.getLogger('sql2api')
bp = Blueprint('api', __name__)

# Query-string arguments that control a request rather than supplying query parameters.
RESERVED_ARGS = {'format', 'page', 'page_size', 'connection_name', 'version', 'timeout'}
PUBLIC_ENDPOINTS = {'api.index', 'api.favicon', 'api.health', 'api.docs', 'api.openapi_spec'}


class JSONProvider(DefaultJSONProvider):
    default = staticmethod(json_default)
    sort_keys = False  # keep result columns in the order the query returned them


def create_app():
    from . import __version__
    app = Flask(__name__)
    app.json = JSONProvider(app)
    app.config['SQL2API_VERSION'] = __version__

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify({'error': error.message, **error.extra}), error.status

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({'error': error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        log.exception('Unhandled error')
        return jsonify({'error': 'An error occurred'}), 500

    @app.before_request
    def require_api_key():
        expected = config.api_key()
        if expected and request.endpoint not in PUBLIC_ENDPOINTS:
            # compare_digest rejects non-ASCII str, so compare bytes
            supplied = request.headers.get('X-API-Key', '').encode('utf-8', 'replace')
            if not hmac.compare_digest(supplied, expected.encode('utf-8')):
                return jsonify({'error': 'Unauthorized'}), 401

    app.register_blueprint(bp)
    return app


# --------------------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------------------

def get_json_body(required=True):
    data = request.get_json(silent=True)
    if data is None and not required:
        return {}
    if not isinstance(data, dict):
        raise ApiError('Request body must be a JSON object')
    return data


def get_object(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ApiError(f'{label} must be a JSON object')
    return value


def get_int(value, label):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(f'{label} must be an integer') from None


def get_pagination():
    """Return (limit, offset, page) from the ?page and ?page_size query parameters."""
    page = get_int(request.args.get('page'), 'page')
    page_size = get_int(request.args.get('page_size'), 'page_size')
    page = 1 if page is None else page
    page_size = 10 if page_size is None else page_size
    if page < 1 or page_size < 1:
        raise ApiError('page and page_size must be positive')
    if page_size > config.max_page_size():
        raise ApiError(f'page_size must not exceed {config.max_page_size()}')
    return page_size, (page - 1) * page_size, page


def get_output_format(body=None):
    output_format = str(request.args.get('format') or (body or {}).get('format') or 'json').lower()
    if output_format not in FORMATTERS:
        raise ApiError(f"Unsupported format '{output_format}'. Supported formats: {', '.join(FORMATTERS)}")
    return output_format


def get_timeout(body=None):
    """Seconds allowed for the query: ?timeout= may lower the server limit but never raise it."""
    raw = request.args.get('timeout', (body or {}).get('timeout'))
    if raw in (None, ''):
        return config.effective_timeout(None)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiError('timeout must be a number of seconds') from None
    if not math.isfinite(value) or value <= 0:
        raise ApiError('timeout must be a positive number of seconds')
    return config.effective_timeout(value)


def render(result, output_format, page, page_size):
    response = jsonify({'message': 'No results returned'}) if not result else FORMATTERS[output_format](result)
    response.headers['X-Page'] = str(page)
    response.headers['X-Page-Size'] = str(page_size)
    response.headers['X-Has-More'] = 'true' if result.has_more else 'false'
    return response


# --------------------------------------------------------------------------------------
# Query execution
# --------------------------------------------------------------------------------------

@bp.route('/execute_sql', methods=['POST'])
def execute_sql_endpoint():
    data = get_json_body()
    if not data.get('sql'):
        raise ApiError('SQL query is missing')
    if not data.get('connection_name'):
        raise ApiError('Connection name is missing')
    params = get_object(data.get('params'), 'params')
    output_format = get_output_format(data)
    timeout = get_timeout(data)
    limit, offset, page = get_pagination()
    result = engine.execute_sql(data['sql'], data['connection_name'], limit, offset, params, timeout)
    return render(result, output_format, page, limit)


def run_saved(ref, body, url_params):
    """Execute a saved query (latest version unless one is requested) and record the run."""
    path = store.resolve_saved_file(ref)
    number, saved = store.select_version(store.load_versions(path),
                                         get_int(request.args.get('version') or body.get('version'), 'version'))
    connection_name = request.args.get('connection_name') or body.get('connection_name') \
        or saved.get('connection_name')
    if not connection_name:
        raise ApiError('Connection name is missing')
    if not isinstance(saved.get('sql_query'), str):
        raise ApiError('Saved query has no SQL', 500)

    raw = {**url_params, **get_object(body.get('params'), 'params'),
           **get_object(body.get('placeholders'), 'placeholders')}
    params = sqltools.coerce_params(saved.get('query_parameters'), raw)
    sql = sqltools.fill_placeholders(saved['sql_query'], params)
    output_format = get_output_format(body)
    timeout = get_timeout(body)
    limit, offset, page = get_pagination()

    entry = {'executed_at': store.now(), 'connection_name': connection_name}
    try:
        result, elapsed_ms = engine.timed(engine.execute_sql, sql, connection_name, limit, offset, params, timeout)
    except ApiError as error:
        store.record_execution(path, number, {**entry, 'status': 'error', 'error': error.message})
        raise
    store.record_execution(path, number, {**entry, 'status': 'success', 'rows': len(result.rows),
                                          'duration_ms': elapsed_ms})
    return render(result, output_format, page, limit)


@bp.route('/execute_sql_from_file', methods=['POST'])
@bp.route('/execute_sql_with_parameters_from_file', methods=['POST'])
def execute_sql_from_file():
    body = get_json_body()
    return run_saved(body.get('filepath'), body, {})


@bp.route('/q/<name>', methods=['GET', 'POST'])
def run_named_query(name):
    body = get_json_body(required=False) if request.method == 'POST' else {}
    url_params = {k: v for k, v in request.args.items() if k not in RESERVED_ARGS}
    return run_saved(name, body, url_params)


# --------------------------------------------------------------------------------------
# Saved queries
# --------------------------------------------------------------------------------------

@bp.route('/view_file_content', methods=['GET'])
def view_file_content():
    path = store.resolve_saved_file(request.args.get('filename'))
    with open(path, 'r') as f:
        return jsonify({'content': f.read()}), 200


@bp.route('/save_sql_to_file', methods=['PATCH'])
def save_sql_to_file():
    data = get_json_body()
    for field, label in (('author', 'Author'), ('description', 'Description'),
                         ('sql_query', 'SQL query'), ('filename', 'Filename')):
        if not data.get(field) or not isinstance(data[field], str):
            raise ApiError(f'{label} is missing')
    tags = data.get('tags', [])
    if not isinstance(tags, (list, str)):
        raise ApiError('tags must be a string or a list')
    query_parameters = get_object(data.get('query_parameters'), 'query_parameters')
    connection_name = data.get('connection_name')
    if connection_name is not None and not isinstance(connection_name, str):
        raise ApiError('connection_name must be a string')

    query_uuid, version = store.save_version(data['filename'], {
        'sql_query': data['sql_query'],
        'author': data['author'],
        'description': data['description'],
        'tags': tags,
        'query_parameters': query_parameters,
        **({'connection_name': connection_name} if connection_name else {}),
    })
    return jsonify({'message': 'SQL query saved successfully', 'filename': data['filename'],
                    'uuid': query_uuid, 'version': version}), 200


@bp.route('/saved_sql/<name>', methods=['DELETE'])
def delete_saved_query(name):
    version = get_int(request.args.get('version'), 'version')
    store.delete_saved(name, version)
    what = f'Version {version} of {name}' if version is not None else name
    return jsonify({'message': f'{what} deleted'}), 200


@bp.route('/list_files', methods=['GET'])
def list_files():
    sort_by = request.args.get('sort_by', 'name')
    if sort_by not in ('name', 'modified'):
        raise ApiError("sort_by must be 'name' or 'modified'")
    sort_order = request.args.get('sort_order', 'asc')
    if sort_order not in ('asc', 'desc'):
        raise ApiError("sort_order must be 'asc' or 'desc'")

    files = store.list_saved()
    if sort_by == 'name':
        def key(f):
            return f['filename'].lower()
    else:
        def key(f):
            return (f['versions'][-1].get('last_modified_at') or '') if f['versions'] else ''
    files.sort(key=key, reverse=sort_order == 'desc')
    return jsonify({'files': files}), 200


# --------------------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------------------

@bp.route('/connections', methods=['GET'])
def get_connections():
    return jsonify({'connections': store.mask_passwords(store.read_connections())}), 200


@bp.route('/connections', methods=['PATCH'])
def update_connections():
    connections = get_json_body().get('connections')
    if not connections or not isinstance(connections, dict):
        raise ApiError('Connections data is missing')
    store.update_connections(connections)
    return jsonify({'message': 'Connections updated successfully'}), 200


@bp.route('/connections/<name>', methods=['DELETE'])
def delete_connection(name):
    store.delete_connection(name)
    return jsonify({'message': f"Connection '{name}' deleted"}), 200


# --------------------------------------------------------------------------------------
# Service endpoints
# --------------------------------------------------------------------------------------

@bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('api.docs'))


@bp.route('/favicon.ico', methods=['GET'])
def favicon():
    return '', 204


@bp.route('/health', methods=['GET'])
def health():
    from flask import current_app
    return jsonify({'status': 'ok', 'version': current_app.config['SQL2API_VERSION']})


@bp.route('/openapi.json', methods=['GET'])
def openapi_spec():
    from flask import current_app
    return jsonify(openapi.build_spec(current_app.config['SQL2API_VERSION']))


@bp.route('/docs', methods=['GET'])
def docs():
    return Response(openapi.DOCS_HTML, mimetype='text/html')
