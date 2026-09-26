# Hacker News launch kit

Everything you need for a "Show HN" post. The parts to paste are marked **PASTE**; the rest is notes for you.

Facts below match the repo as of v0.7.0 (the release that changed the license to FSL-1.1-MIT). Re-check anything you edit against the README before posting - HN readers
notice a claim that does not hold.

**Read this before posting - the license.** QueryAPIGate is *source-available* (FSL-1.1-MIT), **not open source** by the
OSI definition. On Hacker News, "open source" is checked closely: never call it open source in the title, the comment
or a reply. Say "source-available" and state the terms in one line (already done in the comment below). Some readers
will object to any non-OSI license; that is normal, and the honest answer is in section 4.

---

## 1. Title (pick one)

HN titles are limited to 80 characters. "Show HN:" is required for a project you made, and it goes at the start.

**PASTE** - recommended:

```
Show HN: QueryAPIGate – turn saved SQL queries into governed REST endpoints
```

Alternatives, if you want a different angle:

```
Show HN: Self-hosted service that exposes SQL queries (not schemas) as REST APIs
Show HN: I built an API gateway where the unit is a SQL query, with per-key access
Show HN: QueryAPIGate – scoped API keys for saved SQL queries (MySQL, Postgres, SQLite…)
```

## 2. URL

**PASTE** into the URL field:

```
https://github.com/AnanthaRajuC/QueryAPIGate
```

A Show HN submission is either a URL *or* text, not both. Use the URL, then post the comment in section 3 yourself as
the first comment, immediately after submitting. (Docs, if people ask: https://AnanthaRajuC.github.io/QueryAPIGate/ )

---

## 3. First comment - post this yourself right after submitting

**PASTE** (HN renders paragraphs and indented code blocks; it does not render Markdown):

```
Hi HN, I'm the author. QueryAPIGate is a small self-hosted service (one Flask app) that runs SQL against your
databases and serves the results over HTTP. The unit it exposes is a saved SQL query, not a table or a schema.

The problem I kept running into: someone needs "the monthly revenue numbers" or "one customer by id" as an API.
Tools that expose the whole schema (PostgREST, Hasura and friends) are great, but sometimes you do not want a
client to be able to reach every table - you want exactly one curated query, with typed parameters, handed to one
partner, that stops working on a date. Writing a controller, pagination, auth and serialisation for each one is
the boilerplate I wanted to skip.

So: you save a query once, it becomes a versioned endpoint, and access is decided per API key.

License up front: it is source-available under FSL-1.1-MIT, not open source. You can use it for anything - including
at work - except offering it to others as a competing product or service. Each release becomes plain MIT two years
after it ships. Earlier releases (up to 0.6.1) were MIT; I have withdrawn them, so 0.7.0 is the first under this license.

    $ queryapigate examples load && queryapigate serve
    $ curl 'http://127.0.0.1:5000/q/example_top_films?top_n=3&category=Comedy'

What is in it:

- Saved queries become GET /q/<name>, with :name parameters that are bound (not string-pasted) and validated by
  rules you declare (type, enum, min/max, pattern, default). Versioned, with per-version run history.
- Keys can be scoped to connections, to specific named queries, or to a "collection" of queries. A key granted one
  query can run that query and nothing else - no ad-hoc SQL, no other connection. Keys can also carry an expiry,
  their own rate limit, an IP allowlist, and can be created from reusable roles.
- Read-only by default; writes have to be enabled server-wide, per key, and can be limited to particular statements.
- Streaming CSV/NDJSON exports in constant memory (real server-side cursors for Postgres/MySQL/ClickHouse).
- Every admin change goes to an audit log. Prometheus /metrics, an admin UI, OpenAPI docs that only show a caller
  the queries that caller can actually run, and a Postman export per collection.
- MySQL, PostgreSQL, ClickHouse, SQLite, DuckDB, H2 and generic JDBC. pip install queryapigate.

What it is not: it is not trying to be a GraphQL layer or an ORM, and it does not auto-generate an API from your
schema. It runs SQL that an admin wrote and approved - that is the point, and also why you should give it a database
account with only the privileges the API needs. The read-only guard is defence in depth, not a substitute for grants.

Honest limits: it is one process. Rate limits and the in-app metrics are per process, so with several workers the
effective limit multiplies. Configuration is plain JSON files in a folder, which keeps it simple and easy to back up
but means it is not built for many replicas writing at once.

I would especially like to hear from anyone who has solved this differently, and about the access model - whether
"collections of queries as the unit you grant" matches how you would want to hand data to a partner.

Docs: https://AnanthaRajuC.github.io/QueryAPIGate/
```

Word count is around 480. Do not shorten the "what it is not / honest limits" paragraphs - on HN they earn more
trust than any feature list.

---

## 4. Questions you should expect - have answers ready

Write these in your own words when they come up. Answer everyone, quickly and without defensiveness, especially in
the first two hours.

**"Is this open source?"**
No, and I say so up front. It is source-available under the Functional Source License (FSL-1.1-MIT): the code is public,
you can read, run, modify and self-host it for any purpose that is not a competing use, and every release turns into
MIT two years after it ships. I chose it because I want people to use it freely but not to resell it as a competing
product or hosted service while I am still building it. Versions up to 0.6.1 were released under MIT; I have since withdrawn them, so 0.7.0 is the first release under FSL.

**"Why not just use MIT / AGPL?"**
MIT would let anyone repackage and sell it, which I do not want. AGPL keeps the code open but still allows selling, and
many companies will not touch it. FSL is a middle path with a built-in date when each version becomes MIT, so it is
not a permanent lock. If that is a deal-breaker for you, that is a fair reaction and I would rather you know now.

**"Can I use it at my company / for clients?"**
Yes: internal use is explicitly permitted, and so are professional services you provide to someone who is licensed to
use it. What is not allowed is making it available to others as a commercial product or service that substitutes for
it or offers substantially similar functionality. If your case is unclear, email me - I would rather answer than have
you guess.

**"How is this different from PostgREST / Hasura / Directus?"**
Those model the schema: you point them at tables and get an API over all of them, then restrict with row-level rules.
This models the query: an admin writes the exact SQL, and a key is granted that query. It works across MySQL,
Postgres, ClickHouse and others through one interface. If you want CRUD over your tables, use the schema tools; if you
want to hand out a small, fixed set of answers, this is aimed at that.

**"Isn't running SQL from an HTTP service dangerous?"**
A saved-query endpoint runs SQL an admin wrote, with bound parameters. Ad-hoc SQL exists too (POST /execute_sql), but
only for the admin key and for keys you deliberately grant a whole connection - and it is read-only unless writes are
enabled. A key granted only specific queries or a collection cannot run ad-hoc SQL at all. Layers: read-only by
default (checked per statement, plus a read-only connection where the driver supports it), no multi-statement,
per-key grants, timeouts, rate limits, audit log. And a real database account with minimal privileges underneath -
I say so in the README.

**"Have you found security bugs in your own scoped keys?"**
Yes, and it is worth saying plainly. In 0.6.0 I fixed one: a key granted a saved query could add
`?connection_name=other` and run that query's SQL against a different connection it had no grant on. It is fixed and
covered by tests; the changelog calls it out. I would rather say that than pretend an access-control layer has no
bugs. If you find another, SECURITY.md has how to report it.

**"Why Python/Flask? Isn't that slow?"**
The work is in the database; the service mostly binds parameters and streams rows. It is meant for reports,
dashboards, exports and partner integrations, not for a 50k-requests-per-second hot path. The shipped image runs
gunicorn with threads. I have not published throughput numbers and will not claim any I have not measured.

**"Why JSON files instead of a database?"**
Deliberately simple: a folder you can read, diff, back up and put in version control. The cost is the single-writer
limit mentioned above. If that becomes the constraint for real users, a pluggable store is the obvious next step.

**"Does it work with X?"**
MySQL, PostgreSQL, ClickHouse, SQLite, DuckDB, H2, and anything with a JDBC driver (needs Java). Others: not yet.

**"Why was it renamed?"**
It was called SQL2API; the name was shared by a dozen unrelated projects, so it became QueryAPIGate in 0.5.0
(a clean break, with an upgrade note in the docs).

---

## 5. Posting notes

- **When:** weekday mornings US time tend to work best (roughly 8-10am Eastern). The first hour matters most.
- **Be present:** stay online for a few hours after posting and reply to every comment. That is most of what makes a
  Show HN succeed.
- **Do not ask for upvotes**, and do not ask friends to upvote or comment in a coordinated way. HN detects it and
  penalises the post. Sharing the link with a friend "for feedback" is fine; asking them to vote is not.
- **Do not edit the title** after posting unless a moderator asks.
- **Never write "open source".** Use "source-available". Expect at least one comment about the license; answer it
  calmly, with the same short explanation each time, and do not argue about whether source-available "counts".
- **Do not hide the license.** It is in the first paragraph of your comment on purpose; readers who find it buried
  react much worse than readers who are told upfront.
- **Test the front door first.** In a clean virtualenv on a machine that is not yours: `pip install queryapigate`,
  `queryapigate examples load`, `queryapigate serve`, and the `curl` above. Anyone trying it in the first minute
  should get a working result. Also make sure the README's first screen and the docs site load.
- **Have the repo ready for visitors:** the README leads with what it does and a curl example, the CI badge is green
  and the latest release is visible. A stale badge or an open "TODO" issue is the first thing people see.
- **If it does not take off,** it is normal; a Show HN can be reposted later with meaningful news (a new release, a
  write-up), but do not repost the same thing repeatedly.
- **Criticism** is the useful part. Thank people, fix what is right, and say plainly what you are not going to do
  and why.

## 6. Optional: a shorter version for other places

For a tweet, a Reddit post or a newsletter blurb:

```
QueryAPIGate: self-hosted service that turns saved SQL queries into REST endpoints - with typed, validated
parameters, and API keys scoped to specific queries (not whole databases), with expiry, rate limits and an audit log.
MySQL / Postgres / ClickHouse / SQLite / DuckDB. Source-available (FSL-1.1-MIT). pip install queryapigate
https://github.com/AnanthaRajuC/QueryAPIGate
```
