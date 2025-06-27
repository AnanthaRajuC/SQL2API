## Query Metadata Management

Each saved query contains comprehensive metadata that supports query organization, authoring, and lifecycle management.

## Metadata Field Descriptions

| Field             | Type         | Purpose                     | Example                                          |
|------------------|--------------|-----------------------------|--------------------------------------------------|
| uuid             | String       | Unique identifier per version | `"c031f3ba-8b49-4e74-adf3-b085a12581f8"`        |
| sql_query        | String       | SQL statement content        | `"SELECT * FROM sakila.actor;"`                 |
| author           | String       | Query creator                | `"anantha"`                                     |
| description      | String       | Query documentation          | `"Retrieves all actors from sakila database"`   |
| tags             | String/Array | Classification labels        | `"test,prod"`                                   |
| query_parameters | Object       | Parameter definitions        | `{}`                                            |
| created_at       | String       | Creation timestamp           | `"2024-03-23 23:50:57"`                          |
| last_modified_at | String       | Last update timestamp        | `"2024-03-23 23:50:57"`                          |
| status           | String       | Query state                  | `"active"`                                      |
| version          | Integer      | Version number               | `1`                                              |
| execution_history| Array        | Execution tracking           | `[]`                                             |
