"""One runner per database type: connect (or borrow a pooled connection), run one statement, return (columns, rows).

Runners fetch ``limit + 1`` rows: the extra row is how the caller learns whether another page exists.
Database drivers are imported lazily so only the ones you actually use need to be installed.

Each network database is a small ``_Driver`` subclass. ``_make_runner`` turns it into the callable stored in
``RUNNERS``, which either opens a connection for the single call or borrows one from the pool.
"""
import atexit
import logging
import math
import os
import sqlite3
import time
from pathlib import Path

from . import config
from .errors import ApiError
from .pool import Session, close_pooled_connections
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


# --------------------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------------------

class _Driver:
    """How to connect to, check, reset, query and close one kind of database."""

    def connect(self, details, read_only):
        raise NotImplementedError

    def is_alive(self, session):
        """Cheap check that a connection that sat idle is still usable."""
        return True

    def reset(self, session):
        """Put a used connection back into a clean state: end its transaction so no stale snapshot lingers."""

    def close(self, session):
        session.conn.close()

    def query(self, session, sql, params, limit, offset, read_only, timeout):
        raise NotImplementedError


# MySQL reports 3024 (ER_QUERY_TIMEOUT), MariaDB 1969 (ER_STATEMENT_TIMEOUT)
_MYSQL_TIMEOUT_ERRNOS = (3024, 1969)


class _MySQL(_Driver):
    def connect(self, details, read_only):
        import mysql.connector
        conn = mysql.connector.connect(connection_timeout=config.CONNECT_TIMEOUT, **_connect_args(details))
        if read_only:
            try:
                cursor = conn.cursor()
                cursor.execute('SET SESSION TRANSACTION READ ONLY')
                cursor.close()
            except Exception:
                conn.close()
                raise
        return conn

    def is_alive(self, session):
        return session.conn.is_connected()

    def reset(self, session):
        session.conn.rollback()

    def query(self, session, sql, params, limit, offset, read_only, timeout):
        import mysql.connector
        conn = session.conn
        cursor = conn.cursor()
        try:
            if timeout != session.state.get('timeout'):
                # MySQL limits SELECT statements in milliseconds; MariaDB uses a differently named variable
                # in seconds. 0 removes a limit that an earlier request applied to this pooled connection.
                try:
                    cursor.execute(f'SET SESSION max_execution_time = {_millis(timeout) if timeout else 0}')
                except mysql.connector.Error:
                    try:
                        cursor.execute(f'SET SESSION max_statement_time = {timeout:g}' if timeout
                                       else 'SET SESSION max_statement_time = 0')
                    except mysql.connector.Error:
                        log.warning('This MySQL server supports neither max_execution_time nor '
                                    'max_statement_time; the query time limit is not enforced')
                session.state['timeout'] = timeout
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
            cursor.close()


class _Postgres(_Driver):
    def connect(self, details, read_only):
        import psycopg2
        conn = psycopg2.connect(connect_timeout=config.CONNECT_TIMEOUT, **_connect_args(details, database='dbname'))
        if read_only:
            try:
                conn.set_session(readonly=True)
            except Exception:
                conn.close()
                raise
        return conn

    def is_alive(self, session):
        if session.conn.closed:
            return False
        with session.conn.cursor() as cursor:
            cursor.execute('SELECT 1')
        return True

    def reset(self, session):
        session.conn.rollback()

    def query(self, session, sql, params, limit, offset, read_only, timeout):
        import psycopg2.errors
        conn = session.conn
        with conn.cursor() as cursor:
            if timeout:
                # LOCAL scopes the limit to this transaction, so nothing leaks to the connection's next user
                cursor.execute(f'SET LOCAL statement_timeout = {_millis(timeout)}')
            try:
                result = _fetch_page(cursor, sql, params, 'format', limit, offset)
            except psycopg2.errors.QueryCanceled:
                raise _timed_out(timeout) from None
        if not read_only:
            conn.commit()
        return result


_CLICKHOUSE_TIMEOUT_EXCEEDED = 159


class _ClickHouse(_Driver):
    # The native-protocol Client pings before each query and reconnects by itself, so it needs no
    # is_alive check, and every setting is sent per query, so there is no session state to reset.
    def connect(self, details, read_only):
        from clickhouse_driver import Client
        client_args = {}
        limit = config.query_timeout()
        if limit:
            # Backstop in case the server never answers; the server-side limit below is what normally fires.
            client_args['send_receive_timeout'] = math.ceil(limit) + 5
        return Client(connect_timeout=config.CONNECT_TIMEOUT, **client_args, **_connect_args(details))

    def close(self, session):
        session.conn.disconnect()

    def query(self, session, sql, params, limit, offset, read_only, timeout):
        from clickhouse_driver.errors import ServerException
        sql, args, sliced = _prepare(sql, params, 'pyformat', limit, offset)
        settings = {}
        if timeout:
            settings['max_execution_time'] = math.ceil(timeout)  # whole seconds
        if read_only:
            settings['readonly'] = 1  # last: it forbids changing settings after it
        try:
            result = session.conn.execute(sql, args, with_column_types=True, settings=settings or None)
        except ServerException as error:
            if error.code == _CLICKHOUSE_TIMEOUT_EXCEEDED:
                raise _timed_out(timeout) from None
            raise
        # Statements without a result set (DDL, INSERT) may not return a (rows, types) pair.
        rows, column_types = result if isinstance(result, tuple) else ([], [])
        if not sliced:
            rows = rows[offset:offset + limit + 1]
        return [c[0] for c in column_types or []], rows


def _attach_thread_as_daemon():
    """Make the calling thread a *daemon* thread as far as the JVM is concerned.

    jaydebeapi attaches every thread that uses H2 to the JVM as a non-daemon thread, and JPype's shutdown then
    waits for those threads forever - so a server that has handled concurrent H2 requests would hang on exit.
    Attaching them as daemons first (jaydebeapi only attaches threads that are not attached yet) avoids that.
    """
    import jpype
    if jpype.isJVMStarted() and not jpype.java.lang.Thread.isAttached():
        jpype.java.lang.Thread.attachAsDaemon()


class _H2(_Driver):
    _exit_hook_registered = False

    def connect(self, details, read_only):
        import jaydebeapi
        _attach_thread_as_daemon()
        host = details.get('host') or 'localhost'
        if details.get('port') and ':' not in host:
            host = f"{host}:{details['port']}"
        url = f"jdbc:h2:tcp://{host}/~/{details.get('database')}"
        # Unlike the other drivers, H2's JDBC setReadOnly() is only a hint and does not block writes,
        # so here the read-only guarantee rests on validate_sql() alone.
        conn = jaydebeapi.connect('org.h2.Driver', url, [details.get('user'), details.get('password')],
                                  [config.h2_jar()])
        if not _H2._exit_hook_registered:
            # JPype shuts the JVM down from its own atexit hook, which it registers when the JVM starts (just
            # now). Hooks run last-in first-out, so registering ours after that makes pooled connections close
            # while the JVM is still alive - closing them afterwards would hang the interpreter at exit.
            atexit.register(close_pooled_connections)
            _H2._exit_hook_registered = True
        return conn

    def is_alive(self, session):
        _attach_thread_as_daemon()
        return bool(session.conn.jconn.isValid(2))

    def reset(self, session):
        _attach_thread_as_daemon()
        session.conn.rollback()

    def close(self, session):
        _attach_thread_as_daemon()
        session.conn.close()

    def query(self, session, sql, params, limit, offset, read_only, timeout):
        import jaydebeapi
        _attach_thread_as_daemon()
        conn = session.conn
        cursor = conn.cursor()
        if timeout != session.state.get('timeout'):
            cursor.execute(f'SET QUERY_TIMEOUT {_millis(timeout) if timeout else 0}')
            session.state['timeout'] = timeout
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


def _make_runner(driver):
    def run(details, sql, params, limit, offset, read_only, timeout=None, pool=None):
        if pool is None:
            session = Session(driver.connect(details, read_only), driver)
            try:
                return driver.query(session, sql, params, limit, offset, read_only, timeout)
            finally:
                session.close()
        with pool.checkout(driver, details, read_only) as session:
            return driver.query(session, sql, params, limit, offset, read_only, timeout)

    return run


_run_mysql = _make_runner(_MySQL())
_run_postgres = _make_runner(_Postgres())
_run_clickhouse = _make_runner(_ClickHouse())
_run_h2 = _make_runner(_H2())


def _run_sqlite(details, sql, params, limit, offset, read_only, timeout=None, pool=None):
    """SQLite is a local file, so opening it per call is cheap and it is never pooled."""
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


RUNNERS = {
    'mysql': _run_mysql,
    'postgres': _run_postgres,
    'clickhouse': _run_clickhouse,
    'sqlite': _run_sqlite,
    'h2': _run_h2,
}
