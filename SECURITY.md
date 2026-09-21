# Security Policy

SQL2API executes SQL on behalf of whoever can reach it, so please treat it as a sensitive piece of infrastructure.

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately through GitHub's
["Report a vulnerability"](https://github.com/AnanthaRajuC/SQL2API/security/advisories/new) form on this repository,
or email arcswdev@gmail.com. You can expect an acknowledgement within a few days.

## Supported versions

Security fixes are made against the latest released version.

## Hardening checklist for deployments

- Set `SQL2API_API_KEY`, and put the service behind TLS (a reverse proxy) - the key is sent in a header.
- Leave `SQL2API_ALLOW_WRITES` unset unless you really need writes, and connect with a database account that only
  has the privileges the API should have. The read-only guard is defence in depth, not a substitute for grants.
- Keep credentials out of `db_connections.json`: use `"password": "${ENV_VAR}"` references.
- Do not enable `SQL2API_DEBUG` on a reachable host.
- Prefer bound `:name` parameters over `{name}` text placeholders.
- Note that `GET /connections` reveals hosts, ports, users and database names (passwords are masked).
