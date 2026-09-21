# Installation and setup

## Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.9+ | Runtime |
| Java | 11+ (only for H2) | Runs the H2 JDBC driver via JPype |

## Install

~~~bash
pip install sql2api                     # SQLite only
pip install "sql2api[postgres,mysql]"   # add the drivers you need
pip install "sql2api[all]"              # every driver
~~~

Available extras: `mysql`, `postgres`, `clickhouse`, `h2`, `all`, `server` (gunicorn) and `dev`.
Each database driver is imported only when a connection of that type is used, so you never need drivers you do not use.

| Database | Driver | Extra |
|----------|--------|-------|
| MySQL | `mysql-connector-python` | `mysql` |
| PostgreSQL | `psycopg2-binary` | `postgres` |
| ClickHouse | `clickhouse-driver` | `clickhouse` |
| SQLite | `sqlite3` (standard library) | - |
| H2 | `JayDeBeApi` + `JPype1` | `h2` |

### From source

~~~bash
git clone https://github.com/AnanthaRajuC/SQL2API.git && cd SQL2API
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
~~~

## Set up a data folder

SQL2API keeps its state in one folder - `SQL2API_HOME`, by default the current directory:

~~~
db_connections.json     connection registry
saved_sql/              one JSON file per saved query
~~~

~~~bash
mkdir my-api && cd my-api
sql2api init            # writes db_connections.json (all templates inactive) and saved_sql/
# edit db_connections.json, set "active": true on the connections you want
sql2api serve           # http://127.0.0.1:5000
~~~

To try it without any database of your own, use the bundled examples: `cd examples && cp db_connections.example.json
db_connections.json && sql2api serve`.

## Configuration

Behaviour is controlled by environment variables - see the table in the [README](../README.md#configuration)
(`SQL2API_HOME`, `SQL2API_ALLOW_WRITES`, `SQL2API_API_KEY`, `SQL2API_MAX_PAGE_SIZE`, `SQL2API_QUERY_TIMEOUT`,
`SQL2API_HOST`, `SQL2API_PORT`, `SQL2API_DEBUG`, `SQL2API_H2_JAR`).

## Running in production

`sql2api serve` uses Flask's development server. For production use gunicorn with **one worker** (saved-query and
connection files are protected by an in-process lock) and several threads, behind a TLS-terminating reverse proxy:

~~~bash
pip install "sql2api[server]"
SQL2API_API_KEY=change-me gunicorn --bind 127.0.0.1:5000 --workers 1 --threads 8 "sql2api.app:create_app()"
~~~

Or use the [Dockerfile](../Dockerfile) - see the README.

## Verify

~~~bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/connections
~~~

## Running the tests

~~~bash
pip install -e ".[dev]"
ruff check .
python -m unittest discover -s tests -t .
~~~

Integration tests against real databases are enabled by setting `SQL2API_IT_POSTGRES`, `SQL2API_IT_MYSQL`,
`SQL2API_IT_CLICKHOUSE` and/or `SQL2API_IT_H2` to a JSON connection object - see the header of
`tests/test_integration.py`.
