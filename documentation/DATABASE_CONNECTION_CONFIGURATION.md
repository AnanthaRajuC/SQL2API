# Database connection configuration

Connections live in `db_connections.json` inside the data folder (`SQL2API_HOME`, default: the current directory).
Create a starter file with `sql2api init`, or copy [`examples/db_connections.example.json`](../examples/db_connections.example.json).
The file is re-read on every request, so edits take effect without a restart, and it can also be managed through the
[`/connections` API](API.md#connections).

## File structure

~~~json
{
    "connections": {
        "reporting": {
            "db": "postgres",
            "host": "db.internal",
            "port": 5432,
            "database": "reports",
            "user": "readonly",
            "password": "${REPORTING_PASSWORD}",
            "active": true
        },
        "local-file": {"db": "sqlite", "database": "sqlite-sakila.db", "active": true}
    }
}
~~~

## Supported types

| `db` | Driver | Notes |
|------|--------|-------|
| `mysql` | `mysql-connector-python` | Sessions are opened `READ ONLY` unless writes are enabled |
| `postgres` | `psycopg2` | Sessions are opened read-only unless writes are enabled |
| `clickhouse` | `clickhouse-driver` (native protocol, port 9000) | `readonly=1` unless writes are enabled |
| `sqlite` | `sqlite3` | Opened with `mode=ro` unless writes are enabled |
| `h2` | `JayDeBeApi` + bundled JDBC jar | Connects to a running H2 TCP server: `jdbc:h2:tcp://<host>[:port]/~/<database>` |

The SQL guard (single-statement / read-only check, see [API.md](API.md)) reads string literals using the quoting
rules the connection's `db` type actually uses: `mysql` and `clickhouse` honour a backslash escape inside quoted
strings by default, the others do not, and using the wrong rule for a value can misjudge where a statement ends.

## Query time limit

`SQL2API_QUERY_TIMEOUT` (default 30 seconds) is enforced by each database itself, so the statement is genuinely
cancelled and its resources released rather than merely abandoned:

| `db` | Mechanism | Notes |
|------|-----------|-------|
| `mysql` | `max_execution_time` (MariaDB: `max_statement_time`) | Applies to `SELECT`. MySQL cuts `SLEEP()` and `BENCHMARK()` short but returns normally instead of raising an error. |
| `postgres` | `statement_timeout` | |
| `clickhouse` | `max_execution_time` | Whole seconds, checked as data blocks are processed, so cancellation can lag slightly. |
| `sqlite` | progress handler | Checked every 10 000 VM instructions. |
| `h2` | `SET QUERY_TIMEOUT` | |

## Connection pooling

MySQL, PostgreSQL, ClickHouse and H2 connections are kept open and reused between requests (SQLite is a local file
and is opened per request). Tune it with `SQL2API_POOL_SIZE` (idle connections kept per distinct connection
setting, default 5, `0` disables pooling) and `SQL2API_POOL_IDLE_TIMEOUT` (seconds, default 300).

- **Clean hand-over.** A connection's transaction is ended before it is reused, so a request never sees a stale
  snapshot, and query limits are applied per request (or per transaction) so they never leak to the next user.
- **Errors.** A connection used by a failed or timed-out request is closed rather than reused.
- **Health checks.** A connection that sat idle for more than a few seconds is checked before reuse; a dead one is
  replaced transparently.
- **Changes take effect.** `PATCH`/`DELETE /connections` close all idle pooled connections immediately. If you edit
  `db_connections.json` by hand, old connections are dropped as they reach the idle timeout.
- **Sizing.** The pool bounds *idle* connections, not concurrent ones. Each server process has its own pool, so the
  most idle connections your database sees is roughly `SQL2API_POOL_SIZE` x distinct connections x worker processes;
  keep that below the database's `max_connections`.

## Properties

| Property | Required | Description |
|----------|----------|-------------|
| `db` | yes | One of the types above |
| `active` | yes | Only active connections can be used (otherwise 403) |
| `database` | yes | Database name, or the file path for SQLite (relative paths resolve against the data folder) |
| `host` | network databases | Server host |
| `port` | no | Overrides the driver's default port |
| `user`, `password` | usually | Credentials |

## Keeping secrets out of the file

Any string value may contain `${VAR}` references, replaced with the environment variable's value when the connection is
used (a missing variable is reported as an error naming it). `GET /connections` masks plain-text passwords as
`********` and shows `${VAR}` references as written.

## Best practice

- Use a database account with only the privileges the API needs. The read-only guard is defence in depth.
- Keep `db_connections.json` out of version control (the repository's `.gitignore` already does).
- Use `"active": false` to disable a connection without deleting it.
