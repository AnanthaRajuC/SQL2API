"""Runtime configuration, read from environment variables at call time."""
import os
from pathlib import Path

SUPPORTED_DB_TYPES = ('mysql', 'postgres', 'clickhouse', 'sqlite', 'h2')
PASSWORD_MASK = '********'
CONNECT_TIMEOUT = 10  # seconds
HISTORY_LIMIT = 50  # executions remembered per saved-query version
DEFAULT_QUERY_TIMEOUT = 30.0  # seconds
DEFAULT_POOL_SIZE = 5  # idle connections kept per distinct connection
DEFAULT_POOL_IDLE_TIMEOUT = 300.0  # seconds

# Ships with the package; override with SQL2API_H2_JAR to use a different H2 version.
BUNDLED_H2_JAR = Path(__file__).parent / 'lib' / 'h2-2.2.224.jar'

# Shown by `sql2api init`. Every entry starts inactive so nothing connects until you opt in.
EXAMPLE_CONNECTIONS = {
    'connections': {
        'example-sqlite': {'db': 'sqlite', 'database': 'example.db', 'active': False},
        'example-postgres': {'db': 'postgres', 'host': 'localhost', 'port': 5432, 'database': 'postgres',
                             'user': 'postgres', 'password': '${POSTGRES_PASSWORD}', 'active': False},
        'example-mysql': {'db': 'mysql', 'host': 'localhost', 'port': 3306, 'database': 'mydb',
                          'user': 'root', 'password': '${MYSQL_PASSWORD}', 'active': False},
        'example-clickhouse': {'db': 'clickhouse', 'host': 'localhost', 'port': 9000, 'database': 'default',
                               'user': 'default', 'password': '', 'active': False},
        'example-h2': {'db': 'h2', 'host': 'localhost', 'database': 'test', 'user': 'SA', 'password': '',
                       'active': False},
    }
}


def env_flag(name):
    return os.environ.get(name, '').strip().lower() in ('1', 'true', 'yes', 'on')


def home():
    """Folder holding db_connections.json and saved_sql/ (SQL2API_HOME, default: current directory)."""
    return Path(os.environ.get('SQL2API_HOME') or os.getcwd()).resolve()


def connections_file():
    return home() / 'db_connections.json'


def saved_sql_dir():
    return home() / 'saved_sql'


def h2_jar():
    return os.environ.get('SQL2API_H2_JAR') or str(BUNDLED_H2_JAR)


def allow_writes():
    return env_flag('SQL2API_ALLOW_WRITES')


def api_key():
    return os.environ.get('SQL2API_API_KEY') or None


def query_timeout():
    """Server-wide statement time limit in seconds (SQL2API_QUERY_TIMEOUT); None when disabled (set to 0)."""
    try:
        value = float(os.environ.get('SQL2API_QUERY_TIMEOUT', DEFAULT_QUERY_TIMEOUT))
    except ValueError:
        return DEFAULT_QUERY_TIMEOUT
    if value == 0:
        return None
    return value if value > 0 else DEFAULT_QUERY_TIMEOUT


def effective_timeout(requested=None):
    """The limit to enforce: a request may ask for less time than the server allows, never more."""
    limit = query_timeout()
    if requested is None:
        return limit
    return requested if limit is None else min(requested, limit)


def pool_size():
    """Idle connections kept per distinct connection (SQL2API_POOL_SIZE); 0 disables pooling."""
    try:
        return max(0, int(os.environ.get('SQL2API_POOL_SIZE', DEFAULT_POOL_SIZE)))
    except ValueError:
        return DEFAULT_POOL_SIZE


def pool_idle_timeout():
    """Seconds an idle pooled connection is kept before it is closed (SQL2API_POOL_IDLE_TIMEOUT)."""
    try:
        value = float(os.environ.get('SQL2API_POOL_IDLE_TIMEOUT', DEFAULT_POOL_IDLE_TIMEOUT))
    except ValueError:
        return DEFAULT_POOL_IDLE_TIMEOUT
    return value if value > 0 else DEFAULT_POOL_IDLE_TIMEOUT


def max_page_size():
    try:
        return max(1, int(os.environ.get('SQL2API_MAX_PAGE_SIZE', 1000)))
    except ValueError:
        return 1000
