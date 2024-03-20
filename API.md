## API

This application comes with the following out-of-the-box API's.

### Execute SQL  

Execute SQL passed via the endpoint.

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/execute_sql?format=json`                     | POST   |Direct SQL execution.     | [JSON](#login)            |

~~~json
{
    "sql": "SELECT * FROM streaming_etl_db.geo;"
}
~~~

### Save SQL  

Save SQL to a file to be called at a later point in time.

|                                          URL                       | Method |          Remarks         | Sample Valid Request Body |
|--------------------------------------------------------------------|--------|--------------------------|---------------------------|
|`http://localhost:5000/save_sql_to_file`                            | POST   |Save sql to a file.       | [JSON](#login)            |

~~~json
{
    "sql": "SELECT * FROM sakila.actor",
    "filename": "phn.sql"
}
~~~

http://localhost:5000/list_files?sort_by=name&sort_order=desc
http://localhost:5000/list_files?sort_by=datetime&sort_order=asc
http://localhost:5000/list_files?sort_by=datetime&sort_order=desc