# SQL2API

[![CI](https://github.com/AnanthaRajuC/SQL2API/actions/workflows/ci.yml/badge.svg)](https://github.com/AnanthaRajuC/SQL2API/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

**Turn SQL into a REST API.** SQL2API is a small Flask service that runs SQL against your databases and returns the
results as JSON, NDJSON, CSV, TSV, XML, YAML or Excel. Save a query once and it becomes an endpoint with typed,
injection-safe parameters, versioning and run history.

~~~bash
$ curl 'http://127.0.0.1:5000/q/actor_by_id?id=7'
[{"actor_id": 7, "first_name": "GRACE", "last_name": "MOSTEL"}]

$ curl 'http://127.0.0.1:5000/q/films_by_rating?rating=PG&max_length=60&format=csv&page_size=2'
film_id,title,rating,length
410,HEAVEN FREEDOM,PG,48
443,HURRICANE AFFAIR,PG,49
~~~

| Database   | JSON | NDJSON | XML | YAML | CSV | TSV | XLSX |
|------------|:----:|:------:|:---:|:----:|:---:|:---:|:----:|
| MySQL      | ✅   | ✅     | ✅  | ✅   | ✅  | ✅  | ✅   |
| PostgreSQL | ✅   | ✅     | ✅  | ✅   | ✅  | ✅  | ✅   |
| ClickHouse | ✅   | ✅     | ✅  | ✅   | ✅  | ✅  | ✅   |
| SQLite     | ✅   | ✅     | ✅  | ✅   | ✅  | ✅  | ✅   |
| H2         | ✅   | ✅     | ✅  | ✅   | ✅  | ✅  | ✅   |

## Features

- **Ad-hoc queries** - `POST /execute_sql` with SQL and a connection name.
- **Saved, versioned queries** - every save creates a new version; `GET /q/<name>?id=7` runs the latest one
  (or `?version=1`). Each run is recorded in the query's execution history.
- **Bound parameters** - write `WHERE id = :id` and the value is sent to the database separately from the SQL, so it
  cannot inject anything. Declare types (`{"id": "int"}`) and query-string values are converted for you.
- **Parameter rules** - saved queries can declare defaults, optional parameters, allowed values, numeric ranges and
  text patterns. Bad input is rejected with a field-by-field `400` before it reaches the database.
- **A live catalogue of your endpoints** - `/docs` lists every saved query as its own endpoint with its parameters and
  rules. The SQL itself is never shown, and with an API key set the list is hidden from anonymous readers.
- **Pagination** - `?page=2&page_size=50`, with `X-Has-More` telling you whether another page exists.
- **Connection pooling** - MySQL, PostgreSQL, ClickHouse and H2 connections are reused between requests instead of
  opened for each one (about 30x lower per-request overhead on MySQL and H2 against a local server; more over a network).
- **Query time limit** - runaway queries are cancelled on the database (30 s by default, `?timeout=` per request) so
  they cannot tie up the service.
- **Read-only by default** - only single `SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN` statements run, and sessions are
  opened read-only where the database supports it.
- **Secrets stay out of files** - `"password": "${PG_PASSWORD}"` in `db_connections.json` reads the environment.
- **Self-documenting** - OpenAPI at `/openapi.json`, Swagger UI at `/docs`.

## Install

~~~bash
pip install "sql2api[postgres]"         # pick the drivers you need: mysql, postgres, clickhouse, h2
# or everything:                        pip install "sql2api[all]"
~~~

SQLite needs no extra driver. H2 also needs a Java runtime (the H2 JDBC jar is bundled).
From a clone: `pip install -e ".[dev]"`. Or use Docker - see [below](#docker).

## Quick start

The repository ships two sample SQLite databases and a couple of saved queries:

~~~bash
cd examples
cp db_connections.example.json db_connections.json
sql2api serve                            # http://127.0.0.1:5000
~~~

~~~bash
curl -X POST 'http://127.0.0.1:5000/execute_sql?page_size=3' -H 'Content-Type: application/json' \
     -d '{"sql": "SELECT * FROM actor WHERE actor_id > :min", "params": {"min": 10}, "connection_name": "sakila-sqlite"}'
~~~

Open <http://127.0.0.1:5000/docs> for the interactive API reference.

For your own databases, run `sql2api init` in an empty folder: it creates `db_connections.json` (inactive templates for
every supported database) and `saved_sql/`. Edit the file, set `"active": true`, and start the server there.

## Saving a query as an endpoint

~~~bash
curl -X PATCH http://127.0.0.1:5000/save_sql_to_file -H 'Content-Type: application/json' -d '{
  "filename": "actor_by_id",
  "sql_query": "SELECT * FROM actor WHERE actor_id = :id",
  "query_parameters": {"id": {"type": "int", "min": 1, "max": 200, "description": "Actor id"}},
  "connection_name": "sakila-sqlite",
  "author": "me", "description": "Look up an actor"
}'

curl 'http://127.0.0.1:5000/q/actor_by_id?id=7&format=yaml'
curl 'http://127.0.0.1:5000/q/actor_by_id?id=0'
# {"error": "Invalid parameters: id must be at least 1", "errors": {"id": "must be at least 1"}}
~~~

Rules: `type` (`int`, `float`, `str`, `bool`), `default`, `required`, `enum`, `min`/`max`, `min_length`/`max_length`,
`pattern` and `description` - see [the API reference](documentation/API.md#parameter-rules).

Saving again under the same name adds version 2; `DELETE /saved_sql/actor_by_id?version=1` removes one version.

## Configuration

Everything is configured through environment variables (all optional):

| Variable | Default | Effect |
|----------|---------|--------|
| `SQL2API_HOME` | current directory | Folder holding `db_connections.json` and `saved_sql/`. |
| `SQL2API_ALLOW_WRITES` | off | Allow `INSERT`/`UPDATE`/DDL. Otherwise only single read-only statements are accepted. |
| `SQL2API_API_KEY` | unset | When set, every request (except `/health` and `/docs`) needs a matching `X-API-Key` header. |
| `SQL2API_MAX_PAGE_SIZE` | `1000` | Upper limit for `page_size`. |
| `SQL2API_CORS_ORIGINS` | unset | Websites allowed to call the API from a browser: comma-separated origins such as `https://app.example.com`, or `*`. Off by default. |
| `SQL2API_RATE_LIMIT` | unset | Requests allowed per client address, e.g. `60/minute` (also `second`, `hour`, `day`). Off by default; a malformed value stops startup. |
| `SQL2API_TRUST_PROXY` | `0` | Number of reverse proxies in front of the app whose `X-Forwarded-*` headers are trusted. Set it (usually `1`) behind nginx, a load balancer or a platform router, or every client looks like the proxy. |
| `SQL2API_POOL_SIZE` | `5` | Idle connections kept per distinct connection setting. `0` turns pooling off. |
| `SQL2API_POOL_IDLE_TIMEOUT` | `300` | Seconds an idle pooled connection is kept before it is closed. |
| `SQL2API_QUERY_TIMEOUT` | `30` | Seconds a query may run before it is cancelled (HTTP 504). `0` disables the limit. A request can lower it with `?timeout=`, never raise it. |
| `SQL2API_HOST` / `SQL2API_PORT` | `127.0.0.1` / `5000` | Bind address for `sql2api serve`. |
| `SQL2API_DEBUG` | off | Flask debug mode. Never enable on a reachable host. |
| `SQL2API_H2_JAR` | bundled | Path to a different H2 JDBC jar. |

## Security

SQL2API runs whatever SQL it is given against your databases, so it ships locked down and expects you to finish the job:

- Set `SQL2API_API_KEY` and serve over TLS (put it behind a reverse proxy).
- Connect with a database account that only has the privileges the API needs - the read-only guard is
  defence in depth, not a replacement for grants. (H2's driver cannot enforce read-only, so H2 relies on the guard.)
- Use bound `:name` parameters. The older `{name}` placeholders paste text into the SQL and are therefore restricted
  to numbers and plain text.
- Saved-query files are only read from `saved_sql/`; passwords are never returned by the API.

See [SECURITY.md](SECURITY.md) to report a vulnerability.

### Calling the API from a browser

Browsers refuse cross-origin JSON calls unless the server allows them. List the sites that may call the API:

~~~bash
SQL2API_API_KEY=change-me SQL2API_CORS_ORIGINS=https://app.example.com sql2api serve
~~~

Preflight checks are answered automatically, and the pagination headers (`X-Has-More` etc.) are exposed to the page's
JavaScript. CORS only tells the *browser* which sites may call; it is not authentication, so keep the API key. Avoid
`*` without a key: any website a visitor opens could then reach your databases through their browser (the server logs
a warning if you start that way).

### Rate limiting

`SQL2API_RATE_LIMIT=60/minute` gives each client address a bucket of 60 requests that refills steadily, so short bursts
work but the sustained rate is capped. Over the limit, requests get `429` with a `Retry-After` header, and every
response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`. The limit is applied before the API key check, so
guessing keys is throttled too; `/health` and CORS preflights are never counted. State is per process: with several
workers, the effective limit is multiplied by the number of workers.

## Docker

Every release is published to GitHub Container Registry for `linux/amd64` and `linux/arm64`:

~~~bash
docker run -p 5000:5000 -v "$PWD/data:/data" -e SQL2API_API_KEY=change-me ghcr.io/anantharajuc/sql2api:latest
~~~

| Tag | Contents |
|-----|----------|
| `X.Y.Z`, `latest` | SQL2API with the MySQL, PostgreSQL and ClickHouse drivers (SQLite is built in) |
| `X.Y.Z-h2`, `latest-h2` | The same plus Java and the H2 driver |

The container keeps `db_connections.json` and `saved_sql/` in `/data` (create a starter with
`docker run --rm -v "$PWD/data:/data" ghcr.io/anantharajuc/sql2api sql2api init`). It runs as a non-root user under
gunicorn with one worker (the files are protected by an in-process lock) and a health check on `/health`. Behind a
reverse proxy or load balancer, set `SQL2API_TRUST_PROXY=1`. To build it yourself:
`docker build -t sql2api .` (add `--build-arg WITH_H2=true` for H2).

### Try it with one command

[`docker-compose.yml`](docker-compose.yml) starts SQL2API in front of a PostgreSQL database seeded with sample films:

~~~bash
docker compose up --build
curl -H 'X-API-Key: demo-key' 'http://127.0.0.1:5000/q/films_by_rating?rating=PG&max_length=90'
~~~

Open <http://127.0.0.1:5000/docs>, paste `demo-key` into the box at the top, and both saved queries appear as endpoints.
The demo listens on localhost only, mounts its configuration read-only, and reads the database password from an
environment variable (`${DEMO_DB_PASSWORD}` in [`demo/data/db_connections.json`](demo/data/db_connections.json)).
Clean up with `docker compose down -v`.

## API overview

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/execute_sql` | POST | Run ad-hoc SQL (`sql`, `connection_name`, optional `params`). |
| `/q/<name>` | GET, POST | Run a saved query; query-string or body values become parameters. |
| `/save_sql_to_file` | PATCH | Save a query (creates the next version). |
| `/list_files` | GET | List saved queries and their versions (`sort_by`, `sort_order`). |
| `/saved_sql/<name>` | DELETE | Delete a saved query or one `?version=`. |
| `/view_file_content` | GET | Raw content of a saved query file. |
| `/execute_sql_from_file`, `/execute_sql_with_parameters_from_file` | POST | Run a saved query by `filepath` (same as `/q/<name>`). |
| `/connections` | GET, PATCH | List (passwords masked) / add / update connections. |
| `/connections/<name>` | DELETE | Remove a connection. |
| `/health`, `/docs`, `/openapi.json` | GET | Liveness, Swagger UI, OpenAPI spec. |

Full details are in [documentation/API.md](documentation/API.md).

## Development

~~~bash
pip install -e ".[dev]"
ruff check .
python -m unittest discover -s tests -t .
~~~

The integration tests in `tests/test_integration.py` run against real MySQL, PostgreSQL, ClickHouse and H2 servers when
the matching `SQL2API_IT_*` variables are set, and are skipped otherwise; CI runs them against service containers.
`tests/test_sql_guard_fuzz.py` fuzzes the SQL guard and parameter binder with [Hypothesis](https://hypothesis.readthedocs.io/).
See [CONTRIBUTING.md](CONTRIBUTING.md) for the pull request process, and [CHANGELOG.md](CHANGELOG.md) for what changed.

## Third-party components

The wheel bundles the [H2 Database](https://h2database.com) JDBC driver (MPL 2.0 / EPL 1.0). The sample SQLite
databases in `examples/` derive from the Sakila and Chinook sample datasets.

## License

[MIT](LICENSE) © Anantha Raju C

## Contact

Anantha Raju C - [@anantharajuc](https://twitter.com/anantharajuc) - arcswdev@gmail.com

Project link: <https://github.com/AnanthaRajuC/SQL2API>
