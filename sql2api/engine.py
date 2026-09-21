"""Ties the pieces together: look up the connection, validate the SQL, run it, wrap the page."""
import logging
import time

from . import config, store
from .errors import ApiError
from .formats import ResultSetDTO
from .runners import RUNNERS
from .sqltools import validate_sql

log = logging.getLogger('sql2api')


def execute_sql(sql, connection_name, limit, offset, params=None):
    """Run ``sql`` on a named connection and return the requested page as a ResultSetDTO."""
    details = store.get_connection(connection_name)
    sql = validate_sql(sql)
    log.info('Executing on %s (%s), limit=%s offset=%s: %s', connection_name, details['db'], limit, offset, sql)
    try:
        columns, rows = RUNNERS[details['db']](details, sql, params, limit, offset, not config.allow_writes())
    except ApiError:
        raise
    except ImportError as error:
        log.exception('Missing database driver')
        raise ApiError(f"The driver for '{details['db']}' is not installed", 500, detail=str(error)) from error
    except Exception as error:
        log.exception('Query on %s failed', connection_name)
        raise ApiError('An error occurred while executing the SQL query', 500, detail=str(error)) from error
    has_more = len(rows) > limit
    return ResultSetDTO(rows[:limit], columns, has_more=has_more)


def timed(func, *args, **kwargs):
    """Call ``func`` and return (result, elapsed milliseconds)."""
    started = time.monotonic()
    result = func(*args, **kwargs)
    return result, round((time.monotonic() - started) * 1000)
