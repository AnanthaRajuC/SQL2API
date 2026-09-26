## Technology Stack

### Overview

|Technology                |Description                                      |
|--------------------------|-------------------------------------------------|
|Python                    |High-level, general-purpose programming language.|

### Libraries

|Library                  |Purpose                                                   |
|-------------------------|----------------------------------------------------------|
|Flask                    |HTTP server and routing (gunicorn recommended in production)|
|mysql-connector-python   |MySQL driver                                              |
|psycopg2                 |PostgreSQL driver                                         |
|clickhouse-driver        |ClickHouse driver                                         |
|sqlite3 (stdlib)         |SQLite driver                                             |
|JayDeBeApi + JPype1      |H2 (bundled JDBC jar) and generic `jdbc` connections (your own vendor jar); needs Java|
|duckdb                   |DuckDB driver - embedded database, also queries CSV/JSON/Parquet files directly|
|openpyxl                 |XLSX output                                               |
|PyYAML                   |YAML output                                               |

---

### How it fits together

The `queryapigate` package is a small Flask application:

| Module | Responsibility |
|--------|----------------|
| `app.py` | Flask app factory and HTTP routes |
| `engine.py` | Looks up the connection, validates the SQL, runs it, wraps the page of results |
| `runners.py` | One driver per database type: connect, bind parameters in the driver's style, run, reset |
| `pool.py` | Thread-safe pool of idle connections (reset on return, health-checked, discarded after errors) |
| `sqltools.py` | SQL validation (single statement, read-only), pagination, `:name` binding and `{name}` substitution |
| `formats.py` | Result set and the JSON / NDJSON / CSV / TSV / XML / YAML / XLSX converters |
| `store.py` | Connection registry and saved-query files; all file access is confined to the data folder |
| `config.py` | Environment-variable configuration |
| `openapi.py` | OpenAPI document and the Swagger UI page |
| `cli.py` | `queryapigate serve` / `queryapigate init` |
