# API reference

Base URL when running locally: `http://127.0.0.1:5000`. The same information is available interactively at `/docs`
and as an OpenAPI document at `/openapi.json`.

If the server sets `SQL2API_API_KEY`, send it with every request as `X-API-Key: <key>` (`/health`, `/docs` and
`/openapi.json` are always public).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| [`/execute_sql`](#execute-sql) | POST | Run ad-hoc SQL |
| [`/q/<name>`](#run-a-saved-query) | GET, POST | Run a saved query as an endpoint |
| [`/execute_sql_from_file`](#run-a-saved-query) | POST | Run a saved query by file path |
| [`/execute_sql_with_parameters_from_file`](#run-a-saved-query) | POST | Same as above (kept for compatibility) |
| [`/save_sql_to_file`](#save-a-query) | PATCH | Save a query / add a version |
| [`/list_files`](#list-saved-queries) | GET | List saved queries |
| [`/saved_sql/<name>`](#delete-a-saved-query) | DELETE | Delete a saved query or one version |
| [`/view_file_content`](#view-a-saved-query-file) | GET | Raw saved-query file |
| [`/connections`](#connections) | GET, PATCH | List / add / update connections |
| [`/connections/<name>`](#connections) | DELETE | Delete a connection |
| `/health` | GET | `{"status": "ok", "version": "..."}` |

## Common query parameters

These apply to every endpoint that returns rows.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `format` | `json` | `json`, `ndjson`, `csv`, `tsv`, `xml`, `yaml` or `xlsx`. For the POST endpoints it may also be given in the JSON body. |
| `page` | `1` | 1-based page number. |
| `page_size` | `10` | Rows per page, at most `SQL2API_MAX_PAGE_SIZE` (default 1000). |
| `timeout` | server limit | Seconds the query may run before it is cancelled with a 504. It can lower the server limit (`SQL2API_QUERY_TIMEOUT`, default 30; `0` disables it) but never raise it. For the POST endpoints it may also be given in the JSON body. |

Any trailing `LIMIT`/`OFFSET` in the SQL is replaced by the requested page. Responses carry
`X-Page`, `X-Page-Size` and `X-Has-More` (`true` when another page exists). A query that returns no rows answers
`{"message": "No results returned"}`.

## Execute SQL

`POST /execute_sql?format=json&page=1&page_size=5`

~~~json
{
    "sql": "SELECT * FROM actor WHERE actor_id > :min AND first_name LIKE :name",
    "params": {"min": 10, "name": "A%"},
    "connection_name": "sakila-sqlite"
}
~~~

- `:name` markers are **bound parameters**: values are sent to the database separately from the SQL. Markers inside
  string literals, comments and Postgres `::` casts are ignored. Every marker needs a value in `params`.
- Unless the server sets `SQL2API_ALLOW_WRITES=1`, only a single `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN` or
  `VALUES` statement is accepted (403 otherwise; 400 for several statements).

## Save a query

`PATCH /save_sql_to_file`

~~~json
{
    "filename": "actor_by_id",
    "sql_query": "SELECT * FROM actor WHERE actor_id = :id",
    "query_parameters": {"id": "int"},
    "connection_name": "sakila-sqlite",
    "author": "anantha",
    "description": "Look up an actor",
    "tags": ["example"]
}
~~~

- `filename` may contain letters, digits, spaces, `.`, `_` and `-`. Saving to an existing name creates the next version.
- `query_parameters` declares parameter types (`int`, `float`, `str`, `bool`) used to convert query-string values.
- `connection_name` (optional) is the default connection when a run does not name one.
- Response: `{"message": "...", "filename": "actor_by_id", "uuid": "...", "version": 2}`.

## Run a saved query

`GET /q/actor_by_id?id=7&format=csv` - query-string arguments other than `format`, `page`, `page_size`,
`connection_name` and `version` become parameters.

`POST /q/actor_by_id` - the JSON body may contain `params`, `connection_name`, `version` and `format`:

~~~json
{"params": {"id": 7}, "connection_name": "sakila-sqlite", "version": 1}
~~~

- The latest version runs unless `version` is given.
- `connection_name` from the request wins over the saved default.
- Each run is appended to that version's `execution_history` (last 50 runs: time, connection, status, rows, duration).

The older endpoints `POST /execute_sql_from_file` and `POST /execute_sql_with_parameters_from_file` do the same thing
with the query named in the body:

~~~json
{
    "filepath": "saved_sql/actor_by_id.json",
    "connection_name": "sakila-sqlite",
    "placeholders": {"id": 7},
    "format": "csv"
}
~~~

`filepath` may be a bare name (`actor_by_id`), a path relative to the data folder, or an absolute path - but it must
resolve to a `.json` file inside `saved_sql/`.

### Text placeholders (legacy)

Saved SQL may also contain `{name}` placeholders, which are substituted **as text** before the query runs. Because the
value becomes part of the SQL it must be a number, a boolean, or a string made only of letters, digits, whitespace and
`. , : @ % + / -`; anything else is rejected. Prefer bound `:name` parameters.

## List saved queries

`GET /list_files?sort_by=name&sort_order=desc` - `sort_by` is `name` (default) or `modified`, `sort_order` is `asc`
(default) or `desc`. Returns every query with its versions' metadata (not the SQL text).

## Delete a saved query

`DELETE /saved_sql/actor_by_id` removes the whole query; `DELETE /saved_sql/actor_by_id?version=2` removes one
version (the file goes with its last version).

## View a saved query file

`GET /view_file_content?filename=actor_by_id` returns `{"content": "<raw file text>"}`. Only files in `saved_sql/`
can be read.

## Connections

`GET /connections` lists connections; stored passwords are shown as `********` (values that are `${ENV_VAR}`
references are shown as written).

`PATCH /connections` adds or replaces connections. Sending the `********` mask back for an existing connection keeps
its stored password.

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
        }
    }
}
~~~

`DELETE /connections/reporting` removes one. See [DATABASE_CONNECTION_CONFIGURATION.md](DATABASE_CONNECTION_CONFIGURATION.md)
for the connection fields.

## Errors

Errors are returned as `{"error": "..."}`; failed queries also include `"detail"` with the database's message.

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid input (SQL, paging, format, filename, parameters, several statements) |
| 401 | Missing or wrong `X-API-Key` (only when `SQL2API_API_KEY` is set) |
| 403 | Inactive connection, write statement while writes are disabled, or a file outside `saved_sql/` |
| 404 | Unknown connection, saved query, version or file |
| 500 | The database rejected the query or could not be reached |
| 504 | The query exceeded its time limit and was cancelled (the response includes `"timeout"`) |
