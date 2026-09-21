## Technology Stack

### Overview

|Technology                |Description                                      |
|--------------------------|-------------------------------------------------|
|Python                    |High-level, general-purpose programming language.|

### Libraries

|Library                  |Purpose                                                   |
|-------------------------|----------------------------------------------------------|
|Flask                    |HTTP server and routing                                   |
|mysql-connector-python   |MySQL driver                                              |
|psycopg2                 |PostgreSQL driver                                         |
|clickhouse-driver        |ClickHouse driver                                         |
|sqlite3 (stdlib)         |SQLite driver                                             |
|JayDeBeApi + JPype1      |H2 access through the bundled JDBC jar (needs Java)      |
|openpyxl                 |XLSX output                                               |
|PyYAML                   |YAML output                                               |

---

### How it fits together

`code/SQL2API.py` is a single Flask module:

- **Config and helpers**: paths, environment-variable settings, JSON encoding, error handling and the optional API-key check.
- **Saved queries**: JSON files in `code/saved_sql`, one file per query with a numbered entry per version. All file access is confined to that folder.
- **Connection registry**: `code/db_connections.json`, read on every request so edits take effect without a restart.
- **SQL validation**: single statement only, read-only unless `SQL2API_ALLOW_WRITES` is set; a trailing `LIMIT` is replaced by the requested page.
- **Runners**: one function per database type. Each connects, applies the read-only session setting where the driver supports it, runs the query, closes the connection, and returns `(columns, rows)`.
- **`ResultSetDTO`**: turns columns and rows into JSON, CSV, TSV, XML, YAML or XLSX responses.
