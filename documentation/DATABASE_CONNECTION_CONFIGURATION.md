## Database Connection Configuration

**Purpose and Scope**

This document explains the database connection configuration system in SQL2API, specifically the structure and management of the `db_connections.json` file. This configuration file defines how the Flask application connects to various database systems and manages their connection parameters.

## Configuration File Structure

The SQL2API system uses a centralized JSON configuration file to manage database connections. The configuration is stored in `code/db_connections.json` and follows a nested structure where each connection is identified by a unique key and contains database-specific parameters.

## Supported Database Types

The SQL2API system supports five different database types, each with specific connection parameters and requirements. The following table summarizes the supported database types:

| Database Type | Driver              | Purpose | 
|----------------|----------------------|---------|
| MySQL          | `mysql.connector`    | RDBMS   |
| PostgreSQL     | `psycopg2`           | RDBMS   |
| ClickHouse     | `clickhouse_driver`  | 	Analytical database        |
| H2 Database    | `jaydebeapi`         |  In-memory/embedded database       |
| SQLite         | `sqlite3`            |   File-based database      |

## Connection Properties

| Property  | Type     | Required | Description                      |
|-----------|----------|----------|----------------------------------|
| db        | string   | Yes      | Database type identifier         |
| host      | string   | Yes*     | Database server hostname         |
| user      | string   | Yes*     | Database username                |
| password  | string   | Yes*     | Database password                |
| database  | string   | Yes      | Database name or file path       |
| active    | boolean  | Yes      | Connection availability flag     |

- **Not** required for SQLite connections which only need database (file path)

## Connection Status Management

Each database connection includes an active boolean flag that determines whether the connection is available for use by the SQL2API system. This allows administrators to temporarily disable connections without removing their configuration.

The Flask application uses the active flag to filter available connections when processing API requests. Inactive connections are ignored during connection establishment but remain in the configuration for future activation.

## Configuration Best Practices

When modifying the `db_connections.json` file, follow these guidelines:

- **Unique Connection Keys**: Each connection must have a unique identifier within the `connections` object
- **Required Parameters**: Network-based databases require `host`, `user`, `password`, and `database` parameters
- **Database Type Mapping**: The `db` parameter must match one of the supported database types: `mysql`, `postgres`, `clickhouse`, `h2`, or `sqlite`
- **Active Status**: Use the `active` flag to control connection availability without removing configuration
- **File Paths**: For SQLite connections, use relative or absolute file paths in the `database` parameter






