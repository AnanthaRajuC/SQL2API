## API

This application comes with the following out-of-the-box API's.

- **`/view_file_content`**: Retrieves the content of a specified file.  

- **`/save_sql_to_file`**: Saves SQL queries along with metadata to JSON files.  

-  **`/execute_sql`**: Executes SQL queries and returns results in various formats.  
  
-  **`/execute_sql_with_parameters_from_file`**: Executes SQL queries from files with placeholder substitution.  
  
-  **`/list_files`**: Lists JSON files containing saved SQL queries along with their metadata.  
  
-  **`/connections`**: GET retrieves all database connections, and PATCH updates database connections.  
  
-  **`/execute_sql_from_file`**: Executes SQL queries from files.  

### List DB Connections

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/connections`                                 | GET    |List DB Connections.      |  None                     |

### Create/Update DB Connections

|                                          URL                       | Method |          Remarks            | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|-----------------------------|---------------------------|
|`http://localhost:5000/connections`                                 | PATCH  |Create/Update DB Connections.|  [JSON](#connections)     |

~~~json
{
    "connections": {
        "localhost-test": {
            "database": "test1",
            "db": "test2",
            "host": "localhost",
            "password": "1",
            "user": "default1"
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

### List Saved SQL Files

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/list_files?sort_by=name&sort_order=desc`     | Get    | List saved Files.        |                           |

---

### Execute Saved SQL Files

|                                          URL                                 | Method |          Remarks         | Sample Valid Request Body |
|------------------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/execute_sql_from_file?page_size=2&page=2&offset=1`     | Post   | Execute saved File.      |  [JSON](#login)           |

~~~json
{
    "filepath": "/home/anantha/ARC/experiments/SQL2API/saved_sql/cht.json",
    "connection_name": "localhost-clickhouse",
    "format": "tsv"
}
~~~

~~~json
{
    "filepath": "/home/anantha/ARC/experiments/SQL2API/saved_sql/abc.json",
    "connection_name": "localhost-mysql",
    "format": "tsv"
}
~~~