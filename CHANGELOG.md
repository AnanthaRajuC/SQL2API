# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Docker images are published to GitHub Container Registry on every release (`ghcr.io/anantharajuc/sql2api`, tags
  `X.Y.Z` and `latest`, plus `-h2` variants with Java and the H2 driver), for `linux/amd64` and `linux/arm64`. The
  workflow tests each image before publishing and can be run by hand as a dry run.
- `docker compose up --build` starts a self-contained demo: SQL2API in front of a seeded PostgreSQL database, with
  example saved queries, an API key and a rate limit. CI runs it on every change.
- The image has a `HEALTHCHECK` on `/health`, OCI labels, and access logging.
- Parameter rules for saved queries: besides a type, `query_parameters` can declare `default`, `required`, `enum`,
  `min`/`max`, `min_length`/`max_length`, `pattern` and `description`. Violations are rejected with a 400 that lists
  every problem in an `errors` map; optional parameters without a value are bound as NULL.
- Every saved query is documented as its own endpoint in `/openapi.json` and `/docs`, with its parameters, rules and
  default connection (never its SQL). With an API key set, this section is only shown to authenticated readers, and
  the docs page has a box for the key.
- The Release workflow now refuses to publish when the tag does not match `sql2api.__version__`, is not on `main`,
  or has no dated changelog section.
- CORS support for browser clients (`SQL2API_CORS_ORIGINS`, off by default): allowed origins are echoed back,
  preflight requests are answered without an API key, and the pagination and rate-limit headers are exposed to the
  page. Starting with `*` and no API key logs a warning.
- Rate limiting (`SQL2API_RATE_LIMIT`, e.g. `60/minute`, off by default): a per-client token bucket answering `429` with
  `Retry-After`, plus `X-RateLimit-Limit`/`X-RateLimit-Remaining` headers. It runs before the API key check so key
  guessing is throttled; `/health` and preflights are exempt. A malformed value stops startup.
- `SQL2API_TRUST_PROXY` (number of reverse proxies) makes the app use the client address and scheme from
  `X-Forwarded-*` headers; without it those headers are ignored so they cannot be forged.

### Changed
- Saving a query validates its `query_parameters` and rejects declarations that the SQL does not use.
- Requests rejected by parameter validation are not recorded in `execution_history`.

### Fixed
- The Docker image ran gunicorn with its default 30 second worker timeout, the same as the default query time limit,
  so a query hitting its limit raced gunicorn killing the worker. The timeout is now 120 seconds.
- The OpenAPI document was not valid OpenAPI 3.0 (`exclusiveMinimum: 0` and empty `required` lists), which strict
  tools and client generators reject. It is now validated in the test suite.

## [0.2.0] - 2026-09-21

### Added
- Connection pooling for MySQL, PostgreSQL, ClickHouse and H2: connections are reused between requests instead of
  opened per request (`SQL2API_POOL_SIZE`, default 5 idle connections per distinct setting, `0` disables;
  `SQL2API_POOL_IDLE_TIMEOUT`, default 300 s). Against a local server, per-request time for a trivial query dropped
  from about 14 ms to 0.5 ms on MySQL and H2; ClickHouse barely changed (about 1.2 ms to 1.0 ms).
  Connections are reset between users, health-checked after idling, discarded after errors, and closed at once when
  a connection is changed or deleted through the API.
- Query time limit: statements are cancelled on the database after `SQL2API_QUERY_TIMEOUT` seconds (default 30,
  `0` disables) and the request fails with HTTP 504. A request can lower the limit with `?timeout=` (or a `timeout`
  field in the body) but never raise it. Enforced natively on MySQL/MariaDB, PostgreSQL, ClickHouse, SQLite and H2.

### Changed
- Queries that run longer than 30 seconds are now cancelled by default. Set `SQL2API_QUERY_TIMEOUT=0` to restore the
  previous unlimited behaviour.

### Fixed
- The process could hang on exit after H2 had served concurrent requests: JPype waited forever for worker threads
  that jaydebeapi had attached to the JVM as non-daemon threads. Threads that use H2 are now attached as daemons.

## [0.1.0] - 2026-09-21

First public release, restructured from the original single-file application.

### Added
- Installable `sql2api` package with a `sql2api serve` / `sql2api init` command line and `python -m sql2api`.
- Bound query parameters (`:name`) for every database, so values never become part of the SQL text.
- Saved queries served as endpoints: `GET|POST /q/<name>` with typed parameters and an optional default connection.
- `DELETE /saved_sql/<name>` (whole query or one `?version=`) and `DELETE /connections/<name>`.
- Execution history recorded per saved-query version (last 50 runs, with status, row count and duration).
- `X-Page`, `X-Page-Size` and `X-Has-More` response headers; `ndjson` output format.
- `${ENV_VAR}` references in connection settings so secrets can stay out of `db_connections.json`.
- OpenAPI description at `/openapi.json`, Swagger UI at `/docs` (`/` redirects there), and a `/health` endpoint.
- Read-only-by-default execution (`SQL2API_ALLOW_WRITES`), optional API key (`SQL2API_API_KEY`),
  page size limit (`SQL2API_MAX_PAGE_SIZE`) and configurable data folder (`SQL2API_HOME`).
- Dockerfile, GitHub Actions CI (unit tests plus integration tests against PostgreSQL, MySQL, ClickHouse and H2),
  Dependabot, and runnable examples.

### Changed
- Saved-query and connection files are read from `SQL2API_HOME` (default: the current directory) instead of the
  folder next to the source file; file access is confined to `saved_sql/`.
- Passwords are masked by `GET /connections`.
- Unknown `format` values now return 400; `page_size` is capped; errors use proper HTTP status codes.
- The development server no longer runs in debug mode by default.

### Fixed
- Arbitrary file read through `/view_file_content` and path traversal through saved-query filenames.
- Pagination now works on every database; trailing `LIMIT`/`OFFSET` handling is case-insensitive.
- Database connections are always closed; ClickHouse queries no longer run twice.
- JSON column order is preserved; Decimal, date and driver-specific number types serialise correctly.
- Concurrent saves can no longer lose a version.

[Unreleased]: https://github.com/AnanthaRajuC/SQL2API/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/AnanthaRajuC/SQL2API/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AnanthaRajuC/SQL2API/releases/tag/v0.1.0
