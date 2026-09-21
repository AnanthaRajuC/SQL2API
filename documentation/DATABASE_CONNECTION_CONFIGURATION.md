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
