"""Persistence: the connection registry and the saved-query files (plain JSON on disk).

Everything that touches those files goes through here so that access stays confined to the
configured home folder and read-modify-write cycles are serialised.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime

from . import config
from .errors import ApiError

# Serialises read-modify-write cycles on the JSON files this app manages.
lock = threading.RLock()

_ENV_REF_RE = re.compile(r'\$\{(\w+)\}')
_FILENAME_RE = re.compile(r'^[\w .\-]{1,100}$')


def write_json_atomic(path, data):
    tmp_path = f'{path}.{uuid.uuid4().hex}.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_path, path)


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# --------------------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------------------

def read_connections():
    try:
        with open(config.connections_file(), 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return data.get('connections', {})


def _expand_env(value):
    """Replace ${VAR} references in a connection value with the environment variable's content."""
    if not isinstance(value, str):
        return value

    def replace(match):
        name = match.group(1)
        if name not in os.environ:
            raise ApiError(f"Environment variable '{name}' referenced by the connection is not set", 500)
        return os.environ[name]

    return _ENV_REF_RE.sub(replace, value)


def get_connection(connection_name):
    """Return the usable (active, env-expanded) details of a named connection."""
    if not isinstance(connection_name, str) or not connection_name:
        raise ApiError('Connection name is missing')
    details = read_connections().get(connection_name)
    if not details:
        raise ApiError(f"Connection '{connection_name}' not found", 404)
    if not details.get('active', False):
        raise ApiError(f"The connection '{connection_name}' is currently not active. "
                       "To use it, it must be set to active.", 403)
    if details.get('db') not in config.SUPPORTED_DB_TYPES:
        raise ApiError('Unsupported database type')
    return {key: _expand_env(value) for key, value in details.items()}


def mask_passwords(connections):
    """Hide stored passwords; ${VAR} references are not secrets and stay visible."""
    def mask(conn):
        password = conn.get('password')
        if password and not _ENV_REF_RE.fullmatch(str(password)):
            return {**conn, 'password': config.PASSWORD_MASK}
        return conn

    return {name: mask(conn) for name, conn in connections.items()}


def update_connections(connections):
    for name, details in connections.items():
        if not isinstance(details, dict) or details.get('db') not in config.SUPPORTED_DB_TYPES:
            raise ApiError(f"Connection '{name}' must be an object whose 'db' is one of: "
                           f"{', '.join(config.SUPPORTED_DB_TYPES)}")
    with lock:
        existing = read_connections()
        for name, details in connections.items():
            # GET masks passwords, so a client echoing the mask back means "keep the current one".
            if details.get('password') == config.PASSWORD_MASK and name in existing:
                details = {**details, 'password': existing[name].get('password', '')}
            existing[name] = details
        config.home().mkdir(parents=True, exist_ok=True)
        write_json_atomic(config.connections_file(), {'connections': existing})


def delete_connection(name):
    with lock:
        existing = read_connections()
        if name not in existing:
            raise ApiError(f"Connection '{name}' not found", 404)
        del existing[name]
        write_json_atomic(config.connections_file(), {'connections': existing})


# --------------------------------------------------------------------------------------
# Saved queries (all access is confined to the saved_sql folder)
# --------------------------------------------------------------------------------------

def saved_path_for_name(filename):
    """Path of the saved-query file for a client-supplied name (without extension)."""
    if not isinstance(filename, str) or not _FILENAME_RE.match(filename) or filename.startswith('.'):
        raise ApiError("Filename may only contain letters, digits, spaces, '.', '_' and '-'")
    return os.path.join(config.saved_sql_dir(), f'{filename}.json')


def resolve_saved_file(ref):
    """Resolve a client-supplied file reference to an existing .json file inside the saved_sql folder.

    Accepts a bare name ("cht" or "cht.json"), a path relative to the home folder
    ("saved_sql/cht.json") or an absolute path - as long as it ends up in the saved_sql folder.
    """
    if not isinstance(ref, str) or not ref.strip():
        raise ApiError('Filename is missing')
    saved_dir = str(config.saved_sql_dir())
    if os.path.isabs(ref):
        candidate = ref
    elif os.sep in ref or '/' in ref:
        candidate = os.path.join(config.home(), ref)
    else:
        candidate = os.path.join(saved_dir, ref if ref.endswith('.json') else f'{ref}.json')
    candidate = os.path.realpath(candidate)
    if os.path.dirname(candidate) != os.path.realpath(saved_dir) or not candidate.endswith('.json'):
        raise ApiError('Only .json files inside the saved_sql folder can be accessed', 403)
    if not os.path.isfile(candidate):
        raise ApiError('File not found', 404)
    return candidate


def load_versions(path):
    try:
        with open(path, 'r') as f:
            content = json.load(f)
    except json.JSONDecodeError:
        raise ApiError('Saved query file is not valid JSON', 500) from None
    if not isinstance(content, dict):
        raise ApiError('Saved query file has an unexpected structure', 500)
    return content


def version_numbers(content):
    return [int(v) for v in content if v.isdigit()]


def select_version(content, version=None):
    """Return (number, data) for the requested version, or the latest one when none is given."""
    if version is None:
        numbers = version_numbers(content)
        if not numbers:
            raise ApiError('No valid versions found in the file')
        version = max(numbers)
    data = content.get(str(version))
    if not isinstance(data, dict):
        raise ApiError(f'Version {version} not found', 404)
    return int(version), data


def save_version(filename, fields):
    """Store ``fields`` as the next version of a saved query; returns (uuid, version number)."""
    path = saved_path_for_name(filename)
    query_uuid = str(uuid.uuid4())
    timestamp = now()
    with lock:
        os.makedirs(config.saved_sql_dir(), exist_ok=True)
        versions = load_versions(path) if os.path.exists(path) else {}
        number = max(version_numbers(versions), default=0) + 1
        versions[str(number)] = {
            'uuid': query_uuid,
            **fields,
            'created_at': timestamp,
            'last_modified_at': timestamp,
            'status': 'active',
            'version': number,
            'execution_history': [],
        }
        write_json_atomic(path, versions)
    return query_uuid, number


def delete_saved(ref, version=None):
    """Delete a saved query file, or a single version of it (the file goes with its last version)."""
    path = resolve_saved_file(ref)
    with lock:
        if version is None:
            os.remove(path)
            return
        content = load_versions(path)
        if str(version) not in content:
            raise ApiError(f'Version {version} not found', 404)
        del content[str(version)]
        if version_numbers(content):
            write_json_atomic(path, content)
        else:
            os.remove(path)


def record_execution(path, version, entry):
    """Append to a saved version's execution_history (newest last, capped). Never raises."""
    try:
        with lock:
            content = load_versions(path)
            data = content.get(str(version))
            if not isinstance(data, dict):
                return
            history = data.setdefault('execution_history', [])
            history.append(entry)
            del history[:-config.HISTORY_LIMIT]
            write_json_atomic(path, content)
    except (OSError, ApiError):
        pass


def list_saved():
    """Return every saved query with its versions' metadata (SQL text is not included)."""
    saved_dir = str(config.saved_sql_dir())
    if not os.path.isdir(saved_dir):
        raise ApiError('Folder not found', 404)
    files = []
    for filename in os.listdir(saved_dir):
        file_path = os.path.join(saved_dir, filename)
        if not (os.path.isfile(file_path) and filename.endswith('.json')):
            continue
        try:
            content = load_versions(file_path)
        except ApiError:
            continue
        versions = [{
            'version': int(version),
            'author': data.get('author'),
            'description': data.get('description'),
            'tags': data.get('tags', []),
            'query_parameters': data.get('query_parameters', {}),
            'connection_name': data.get('connection_name'),
            'created_at': data.get('created_at'),
            'last_modified_at': data.get('last_modified_at'),
            'status': data.get('status'),
            'execution_history': data.get('execution_history', []),
        } for version, data in content.items() if version.isdigit() and isinstance(data, dict)]
        versions.sort(key=lambda v: v['version'])
        files.append({'filename': filename[:-5], 'versions': versions})
    return files
