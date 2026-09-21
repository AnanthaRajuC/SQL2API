"""One runner per database type. Each connects, runs one statement, closes, and returns (columns, rows).

Runners fetch ``limit + 1`` rows: the extra row is how the caller learns whether another page exists.
Database drivers are imported lazily so only the ones you actually use need to be installed.
"""
import os
import sqlite3
from pathlib import Path

from . import config
from .errors import ApiError
from .sqltools import bind_parameters, is_paginated, paginate


def _connect_args(details, **renames):
    """Pick the standard connection fields out of a stored connection, renaming keys per driver."""
    args = {}
    for key in ('host', 'port', 'user', 'password', 'database'):
        if details.get(key) not in (None, ''):
            args[renames.get(key, key)] = details[key]
    return args


def _prepare(sql, params, style, limit, offset):
    """Return (sql, args, sliced) - the statement to send, its bound arguments and whether the
    database already applied the requested window (LIMIT/OFFSET) for us."""
    window = limit + 1
    if is_paginated(sql):
        sql, sliced = paginate(sql, window, offset), True
    else:
        sliced = False
    sql, args = bind_parameters(sql, params or {}, style)
    return sql, args, sliced


def _fetch_page(cursor, sql, params, style, limit, offset):
    sql, args, sliced = _prepare(sql, params, style, limit, offset)
    if args is None:
        cursor.execute(sql)
    else:
        cursor.execute(sql, args)
    if not cursor.description:
        return [], []
    rows = cursor.fetchall() if sliced else cursor.fetchmany(offset + limit + 1)[offset:]
    return [d[0] for d in cursor.description], rows


def _run_mysql(details, sql, params, limit, offset, read_only):
    import mysql.connector
    conn = mysql.connector.connect(connection_timeout=config.CONNECT_TIMEOUT, **_connect_args(details))
    try:
        cursor = conn.cursor()
        if read_only:
            cursor.execute('SET SESSION TRANSACTION READ ONLY')
        result = _fetch_page(cursor, sql, params, 'format', limit, offset)
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


def _run_postgres(details, sql, params, limit, offset, read_only):
    import psycopg2
    conn = psycopg2.connect(connect_timeout=config.CONNECT_TIMEOUT, **_connect_args(details, database='dbname'))
    try:
        if read_only:
            conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            result = _fetch_page(cursor, sql, params, 'format', limit, offset)
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


def _run_clickhouse(details, sql, params, limit, offset, read_only):
    from clickhouse_driver import Client
    client = Client(connect_timeout=config.CONNECT_TIMEOUT, **_connect_args(details))
    try:
        sql, args, sliced = _prepare(sql, params, 'pyformat', limit, offset)
        result = client.execute(sql, args, with_column_types=True,
                                settings={'readonly': 1} if read_only else None)
        # Statements without a result set (DDL, INSERT) may not return a (rows, types) pair.
        rows, column_types = result if isinstance(result, tuple) else ([], [])
        if not sliced:
            rows = rows[offset:offset + limit + 1]
        return [c[0] for c in column_types or []], rows
    finally:
        client.disconnect()


def _run_sqlite(details, sql, params, limit, offset, read_only):
    path = details.get('database')
    if not path:
        raise ApiError('Database file path not provided')
    if not os.path.isabs(path):
        path = os.path.join(config.home(), path)
    if not os.path.isfile(path):
        raise ApiError('SQLite database file not found', 404)
    if read_only:
        conn = sqlite3.connect(f'{Path(path).as_uri()}?mode=ro', uri=True, timeout=config.CONNECT_TIMEOUT)
    else:
        conn = sqlite3.connect(path, timeout=config.CONNECT_TIMEOUT)
    try:
        cursor = conn.cursor()
        result = _fetch_page(cursor, sql, params, 'qmark', limit, offset)
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


def _run_h2(details, sql, params, limit, offset, read_only):
    import jaydebeapi
    host = details.get('host') or 'localhost'
    if details.get('port') and ':' not in host:
        host = f"{host}:{details['port']}"
    url = f"jdbc:h2:tcp://{host}/~/{details.get('database')}"
    conn = jaydebeapi.connect('org.h2.Driver', url, [details.get('user'), details.get('password')],
                              [config.h2_jar()])
    try:
        # Unlike the other drivers, H2's JDBC setReadOnly() is only a hint and does not block writes,
        # so here the read-only guarantee rests on validate_sql() alone.
        cursor = conn.cursor()
        result = _fetch_page(cursor, sql, params, 'qmark', limit, offset)
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


RUNNERS = {
    'mysql': _run_mysql,
    'postgres': _run_postgres,
    'clickhouse': _run_clickhouse,
    'sqlite': _run_sqlite,
    'h2': _run_h2,
}
