"""Runtime configuration, read from environment variables at call time."""
import os
from pathlib import Path

SUPPORTED_DB_TYPES = ('mysql', 'postgres', 'clickhouse', 'sqlite', 'h2')
PASSWORD_MASK = '********'
CONNECT_TIMEOUT = 10  # seconds
HISTORY_LIMIT = 50  # executions remembered per saved-query version

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


def max_page_size():
    try:
        return max(1, int(os.environ.get('SQL2API_MAX_PAGE_SIZE', 1000)))
    except ValueError:
        return 1000
