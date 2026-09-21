## API

This application comes with the following out-of-the-box API's.

- **`/view_file_content`**: Retrieves the content of a specified file.  

- **`/save_sql_to_file`**: Saves SQL queries along with metadata to JSON files.  

-  **`/execute_sql`**: Executes SQL queries and returns results in various formats.  
  
-  **`/execute_sql_with_parameters_from_file`**: Executes SQL queries from files with placeholder substitution.  
  
-  **`/list_files`**: Lists JSON files containing saved SQL queries along with their metadata.  
  
-  **`/connections`**: GET retrieves all database connections, and PATCH updates database connections.  
  
-  **`/execute_sql_from_file`**: Executes SQL queries from files.  

## Route Endpoint Details

| Endpoint                                | Method | Handler Function                           | File             |
|-----------------------------------------|--------|---------------------------------------------|------------------|
| `/execute_sql`                          | POST   | `execute_sql_endpoint()`                    | `code/SQL2API.py`|
| `/execute_sql_from_file`               | POST   | `execute_sql_from_file()`                  | `code/SQL2API.py`|
| `/execute_sql_with_parameters_from_file` | POST   | `execute_sql_with_parameters_from_file()`  | `code/SQL2API.py`|
| `/save_sql_to_file`                    | PATCH  | `save_sql_to_file()`                       | `code/SQL2API.py`|
| `/list_files`                          | GET    | `list_files()`                             | `code/SQL2API.py`|
| `/view_file_content`                  | GET    | `view_file_content()`                      | `code/SQL2API.py`|
| `/connections`                         | GET    | `get_connections()`                        | `code/SQL2API.py`|
| `/connections`                         | PATCH  | `update_connections()`                     | `code/SQL2API.py`|

### List DB Connections

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/connections`                                 | GET    |List DB Connections.      |  None                     |

### Create/Update DB Connections

|                                          URL                       | Method |          Remarks            | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|-----------------------------|---------------------------|
|`http://localhost:5000/connections`                                 | PATCH  |Create/Update DB Connections.|  [JSON](#connections)     |

`db` must be one of `mysql`, `postgres`, `clickhouse`, `sqlite`, `h2`. A connection is only usable when `"active": true`.
`GET /connections` masks passwords as `********`; sending that mask back in a PATCH keeps the stored password.

~~~json
{
    "connections": {
        "localhost-test": {
            "database": "test1",
            "db": "postgres",
            "host": "localhost",
            "password": "1",
            "user": "default1",
            "active": true
        }
    }        
}
~~~

---  

### Execute SQL Directly from an endpoint

Execute SQL passed via the endpoint.

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/execute_sql?format=json&page_size=5&page=1`  | POST   |Direct SQL execution.     | [JSON](#api)              |

Query parameters: `format` (`json` default, `csv`, `tsv`, `xml`, `yaml`, `xlsx`), `page` (default 1) and `page_size` (default 10, max 1000).
Any trailing `LIMIT`/`OFFSET` in the SQL is replaced by the requested page. Only single read-only statements are accepted unless the server sets `SQL2API_ALLOW_WRITES=1`.

~~~json
{
    "sql": "SELECT * FROM sakila.film_category;",
    "connection_name": "localhost-mysql"
}
~~~

~~~json
{
    "sql": "SELECT * FROM sakila.film_category",
    "connection_name": "localhost-clickhouse"
}
~~~

~~~json
{
    "sql": "SELECT * FROM playground",
    "connection_name": "localhost-postgres"
}
~~~

~~~json
{
    "sql": "SELECT * FROM actor",
    "connection_name": "localhost-sqlite"
}
~~~

--- 

### Save SQL  

Save SQL to a file to be called at a later point in time.

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/save_sql_to_file`                            | PATCH  |Save sql to a file.       | [JSON](#login)            |

~~~json
{
    "sql_query": "SELECT id FROM sakila.film_category;",
    "author": "anantha",
    "description": "clickhouse 22 test doc",
    "tags": "test,prod",
    "filename": "clickhouse query for sfc updated3.",
    "query_parameters": {},
    "status": "active",
    "execution_history": []
}
~~~

Filenames may contain letters, digits, spaces, `.`, `_` and `-`. Saving to an existing filename creates the next version.

### List Saved SQL Files

`sort_by` is `name` (default) or `modified`; `sort_order` is `asc` (default) or `desc`.

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/list_files?sort_by=name&sort_order=desc`     | Get    | List saved Files.        |                           |

---

### Execute Saved SQL Files

`filepath` may be a bare name (`cht`), a path relative to `code/` (`saved_sql/cht.json`) or an absolute path, but it must resolve to a `.json` file inside `code/saved_sql`.
`format` can be given in the body (as below) or as a query parameter. The latest version of the query is executed.

|                                          URL                                 | Method |          Remarks         | Sample Valid Request Body |
|------------------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/execute_sql_from_file?page_size=2&page=2`     | Post   | Execute saved File.      |  [JSON](#login)           |

~~~json
{
    "filepath": "saved_sql/cht.json",
    "connection_name": "localhost-clickhouse",
    "format": "tsv"
}
~~~

~~~json
{
    "filepath": "saved_sql/abc.json",
    "connection_name": "localhost-mysql",
    "format": "tsv"
}
~~~

### Execute Saved SQL Files with Parameters

Placeholders written as `{name}` in the saved SQL are replaced with the values in `placeholders`.
Values must be numbers, booleans or text made of letters, digits, whitespace and `. , : @ % + / -`; anything else is rejected with a 400, as is a placeholder with no value.

|                                          URL                                            | Method |
|-----------------------------------------------------------------------------------------|--------|
|`http://localhost:5000/execute_sql_with_parameters_from_file?page_size=10&page=1`        | Post   |

~~~json
{
    "filepath": "saved_sql/by_actor.json",
    "connection_name": "localhost-sqlite",
    "placeholders": {"actor_id": 3}
}
~~~

### View a Saved SQL File

`GET http://localhost:5000/view_file_content?filename=cht` returns the raw file content. Only files in `code/saved_sql` can be read.

### Errors

Errors are returned as `{"error": "..."}` (plus a `"detail"` with the database's message for failed queries).

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid input (SQL, paging, format, filename, placeholders, multiple statements) |
| 401 | Missing or wrong `X-API-Key` (only when `SQL2API_API_KEY` is set) |
| 403 | Inactive connection, write statement while writes are disabled, or file outside `saved_sql` |
| 404 | Unknown connection or saved file |
| 500 | The database rejected the query or could not be reached |
