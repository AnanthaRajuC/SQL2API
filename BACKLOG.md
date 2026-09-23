# Backlog

Work that has been discussed but not built, in priority order (highest first). This is a planning
document, not a promise - items move, merge, or drop as the project's needs become clearer. See
[CHANGELOG.md](CHANGELOG.md) for what has already shipped.

Each item has an **Impact** (why it matters for a production-grade, multi-user deployment) and, where the
sizing isn't obvious, a **Notes** line on approach and what it can reuse from the existing code.

## 1. Per-key API permissions

**Impact:** the single biggest gap between "works for one trusted team" and "safe to deploy broadly."
Today one `SQL2API_API_KEY` grants full access to every connection, every saved query and every
administrative action. A serious multi-team or multi-tenant deployment cannot ship on a single shared
bearer key.
**Notes:** needs real design work before implementation - key storage (hashed, not the plaintext-file
pattern `db_connections.json` uses today), what a "permission" scopes over (connections named, `ALLOW_WRITES`
per key, saved-query namespaces), and how it interacts with `SQL2API_ALLOW_WRITES` being a single
server-wide flag today. This is the item to design carefully rather than build fast.

## 2. Observability: structured logs, request IDs, slow-query log, `/metrics`

**Impact:** a production service that can't be operated safely isn't production-ready. Without this,
diagnosing abuse, incidents, or a slow database is guesswork. Pairs naturally with #1 - request IDs and
audit logging matter far more once requests carry a real caller identity.
**Notes:** structured (JSON) logs with a request ID per call, a log line for queries over some threshold,
and a Prometheus-format `/metrics` endpoint (request counts/latencies by endpoint and status, pool
occupancy, rate-limit rejections).

## 3. Streaming exports

**Impact:** `page_size` is capped at 1000 (`SQL2API_MAX_PAGE_SIZE`); there is currently no way to pull a
full large result set. A tool used for real reporting/export workflows will hit this constantly - it's a
capability gap, not a nice-to-have.
**Notes:** stream CSV/NDJSON directly from the cursor instead of buffering the page in memory; needs care
around the query-timeout and connection-pooling code, since a long-streaming response holds a connection
open for the whole transfer.

## 4. Generalise database support via JDBC

**Impact:** expands the databases SQL2API can reach - Oracle, SQL Server, DB2, Snowflake are common in
"serious" enterprises, and their absence can be a hard blocker to adoption there.
**Notes:** this project already embeds a JVM for H2 via `jaydebeapi`/JPype (`sql2api/runners.py`'s `_H2`
class). The same pattern generalises to any JDBC-compatible database with a `jdbc` connection type -
reuses pooling, the SQL guard, parameter binding and formats unchanged; only `connect()` differs per
database. Low risk, since it extends a pattern already proven in production rather than introducing a new
one.

## 5. Schema browser endpoint

**Impact:** self-service query writing without leaving the API (`GET /connections/<name>/schema` - tables,
columns, types). Meaningfully improves usability; a workaround already exists (querying
`information_schema`/equivalent by hand), so this doesn't block adoption on its own.

## 6. Response caching

**Impact:** a real performance/cost win for read-heavy deployments once there's real traffic to justify it.
**Notes:** opt-in TTL per saved query, `ETag`/`Cache-Control` headers; needs to interact correctly with
the execution-history recording and the read-only guard.

## 7. Admin UI

**Status: shipped**, including the follow-ups originally listed here - connections CRUD (with a proper
password-mask round trip), saved-query CRUD, per-version delete, an execution-history view per version, a
hand-rolled (no-dependency) syntax-highlighted SQL editor, and an ad-hoc SQL runner with page-size presets
and Next/Previous - all as a thin client of the existing JSON API with no new backend logic. Verified with
a 39-assertion real-browser (Playwright) test covering every feature above plus an XSS-payload check, both
unauthenticated and with an API key set.
Still open:
- Schema browser integration once backlog item #5 exists.

## 8. Client SDKs generated from the OpenAPI spec

**Impact:** nicer integration ergonomics for Java, Go, TypeScript, etc. callers. Lower priority since the
raw HTTP API plus the already-published OpenAPI document already gets any language there manually.
**Notes:** run `/openapi.json` through `openapi-generator-cli` - no hand-written logic, and specifically
**no duplication of the SQL guard**: the actual SQL execution still happens in this one service. This is
the right way to "support Java, Go, etc." - not a second server implementation.

## 9. Type checking and CI hardening

**Impact:** maintainability, not user-facing. mypy in CI, a coverage badge, Python 3.14 added to the test
matrix once released.

## 10. Docs site (MkDocs on GitHub Pages)

**Impact:** onboarding/marketing polish once the project has enough adoption to justify a dedicated site
beyond the README and `documentation/` folder.

## Not recommended without a specific hard requirement

### A native JVM server port

Rewriting the whole service (connection handling, pooling, rate limiting, OpenAPI generation, and -
hardest of all - the SQL guard) as a second, independent implementation on the JVM. Only worth it for a
concrete constraint like "must run with zero Python in the environment" - nothing on this list is
currently that constraint.

If this is ever pursued, **do not re-derive the SQL guard from scratch.** The dialect-aware backslash vs.
doubling-only string-literal parsing in `sql2api/sqltools.py` took real access to live MySQL/ClickHouse
servers to get right (see the "Fixed" entry under Unreleased in [CHANGELOG.md](CHANGELOG.md)) - a second,
independently-written parser is exactly the kind of thing likely to quietly reintroduce that class of bug.
Export the cases in `tests/test_sql_guard_fuzz.py` (including the real-server-verified regression) as a
language-agnostic `{sql, dialect, expected}` conformance file, and require any new implementation to pass
it before it's trusted - the same technique used for things like Unicode normalization tables or TLS test
vectors.

---

**Ranking note:** this order optimises for "safe and operable in production." If the goal were adoption
and growth instead, the Admin UI (#7) and JDBC database expansion (#4) would rank far higher - a nicer
interface and broader database reach win users faster than access control or a `/metrics` endpoint ever
will. Re-rank explicitly if that's the actual goal before picking up work from this list.
