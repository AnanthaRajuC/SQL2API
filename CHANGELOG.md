# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

First public release, restructured from the original single-file application.

### Added
- Installable `sql2api` package with a `sql2api serve` / `sql2api init` command line and `python -m sql2api`.
- Bound query parameters (`:name`) for every database, so values never become part of the SQL text.
- Saved queries served as endpoints: `GET|POST /q/<name>` with typed parameters and an optional default connection.
- `DELETE /saved_sql/<name>` (whole query or one `?version=`) and `DELETE /connections/<name>`.
- Execution history recorded per saved-query version (last 50 runs, with status, row count and duration).
- `X-Page`, `X-Page-Size` and `X-Has-More` response headers; `ndjson` output format.
- `${ENV_VAR}` references in connection settings so secrets can stay out of `db_connections.json`.
- OpenAPI description at `/openapi.json`, Swagger UI at `/docs`, and a `/health` endpoint.
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
