"""One runner per database type. Each connects, runs one statement, closes, and returns (columns, rows).

Runners fetch ``limit + 1`` rows: the extra row is how the caller learns whether another page exists.
Database drivers are imported lazily so only the ones you actually use need to be installed.
"""
import logging
import math
import os
import sqlite3
import time
from pathlib import Path

from . import config
from .errors import ApiError
from .sqltools import bind_parameters, is_paginated, paginate

log = logging.getLogger('sql2api')


def _timed_out(timeout):
    return ApiError(f'The query exceeded the time limit of {timeout:g} seconds and was cancelled', 504,
                    timeout=timeout)


def _millis(timeout):
    return max(1, int(timeout * 1000))


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


# MySQL reports 3024 (ER_QUERY_TIMEOUT), MariaDB 1969 (ER_STATEMENT_TIMEOUT)
_MYSQL_TIMEOUT_ERRNOS = (3024, 1969)


def _run_mysql(details, sql, params, limit, offset, read_only, timeout=None):
    import mysql.connector
    conn = mysql.connector.connect(connection_timeout=config.CONNECT_TIMEOUT, **_connect_args(details))
    try:
        cursor = conn.cursor()
        if read_only:
            cursor.execute('SET SESSION TRANSACTION READ ONLY')
        if timeout:
            # MySQL limits SELECT statements in milliseconds; MariaDB uses a differently named variable in seconds.
            try:
                cursor.execute(f'SET SESSION max_execution_time = {_millis(timeout)}')
            except mysql.connector.Error:
                try:
                    cursor.execute(f'SET SESSION max_statement_time = {timeout:g}')
                except mysql.connector.Error:
                    log.warning('This MySQL server supports neither max_execution_time nor max_statement_time; '
                                'the query time limit is not enforced')
        try:
            result = _fetch_page(cursor, sql, params, 'format', limit, offset)
        except mysql.connector.Error as error:
            if getattr(error, 'errno', None) in _MYSQL_TIMEOUT_ERRNOS:
                raise _timed_out(timeout) from None
            raise
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


def _run_postgres(details, sql, params, limit, offset, read_only, timeout=None):
    import psycopg2
    import psycopg2.errors
    conn = psycopg2.connect(connect_timeout=config.CONNECT_TIMEOUT, **_connect_args(details, database='dbname'))
    try:
        if read_only:
            conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            if timeout:
                cursor.execute(f'SET statement_timeout = {_millis(timeout)}')
            try:
                result = _fetch_page(cursor, sql, params, 'format', limit, offset)
            except psycopg2.errors.QueryCanceled:
                raise _timed_out(timeout) from None
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


_CLICKHOUSE_TIMEOUT_EXCEEDED = 159


def _run_clickhouse(details, sql, params, limit, offset, read_only, timeout=None):
    from clickhouse_driver import Client
    from clickhouse_driver.errors import ServerException
    client_args = {}
    if timeout:
        # Backstop in case the server never answers; the server-side limit below is what normally fires.
        client_args['send_receive_timeout'] = math.ceil(timeout) + 5
    client = Client(connect_timeout=config.CONNECT_TIMEOUT, **client_args, **_connect_args(details))
    try:
        sql, args, sliced = _prepare(sql, params, 'pyformat', limit, offset)
        settings = {}
        if timeout:
            settings['max_execution_time'] = math.ceil(timeout)  # whole seconds
        if read_only:
            settings['readonly'] = 1  # last: it forbids changing settings after it
        try:
            result = client.execute(sql, args, with_column_types=True, settings=settings or None)
        except ServerException as error:
            if error.code == _CLICKHOUSE_TIMEOUT_EXCEEDED:
                raise _timed_out(timeout) from None
            raise
        # Statements without a result set (DDL, INSERT) may not return a (rows, types) pair.
        rows, column_types = result if isinstance(result, tuple) else ([], [])
        if not sliced:
            rows = rows[offset:offset + limit + 1]
        return [c[0] for c in column_types or []], rows
    finally:
        client.disconnect()


def _run_sqlite(details, sql, params, limit, offset, read_only, timeout=None):
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
        expired = []
        if timeout:
            deadline = time.monotonic() + timeout

            def check_deadline():
                if time.monotonic() > deadline:
                    expired.append(True)
                    return 1  # non-zero aborts the running statement
                return 0

            conn.set_progress_handler(check_deadline, 10000)  # called every 10 000 VM instructions
        cursor = conn.cursor()
        try:
            result = _fetch_page(cursor, sql, params, 'qmark', limit, offset)
        except sqlite3.OperationalError:
            if expired:
                raise _timed_out(timeout) from None
            raise
        if not read_only:
            conn.commit()
        return result
    finally:
        conn.close()


def _run_h2(details, sql, params, limit, offset, read_only, timeout=None):
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
        if timeout:
            cursor.execute(f'SET QUERY_TIMEOUT {_millis(timeout)}')
        try:
            result = _fetch_page(cursor, sql, params, 'qmark', limit, offset)
        except jaydebeapi.Error as error:
            # H2: "Statement was canceled or the session timed out" (error 57014 / 90051)
            if timeout and any(word in str(error).lower() for word in ('canceled', 'timed out')):
                raise _timed_out(timeout) from None
            raise
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
