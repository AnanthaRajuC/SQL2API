"""Pure SQL text handling: validation, pagination, and parameter substitution/binding."""
import math
import re

from . import config
from .errors import ApiError

# Quoted strings, quoted identifiers and comments - text inside these is never inspected.
_LITERAL = r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`[^`]*`|--[^\n]*|/\*.*?\*/"
_LITERALS_RE = re.compile(_LITERAL, re.S)
# A ":name" marker, skipping literals and Postgres "::" casts.
_PARAM_RE = re.compile(rf'(?P<skip>{_LITERAL}|::)|:(?P<name>[A-Za-z_]\w*)', re.S)
_BRACE_RE = re.compile(r'\{(\w+)\}')
_TRAILING_LIMIT_RE = re.compile(r'\s+LIMIT\s+\d+(?:\s*,\s*\d+|\s+OFFSET\s+\d+)?\s*$', re.I)
_SAFE_TEXT_RE = re.compile(r'^[\w\s.,:@%+/\-]*$')

READ_ONLY_STATEMENTS = ('select', 'with', 'show', 'describe', 'desc', 'explain', 'values', 'table')
PAGINATED_STATEMENTS = ('select', 'with')


def first_keyword(sql):
    match = re.match(r'[\s(]*([A-Za-z]+)', _LITERALS_RE.sub(' ', sql))
    return match.group(1).lower() if match else ''


def is_paginated(sql):
    return first_keyword(sql) in PAGINATED_STATEMENTS


def validate_sql(sql):
    """Normalise a client-supplied statement and enforce the single-statement/read-only rules."""
    if not isinstance(sql, str) or not sql.strip():
        raise ApiError('SQL query is missing')
    sql = re.sub(r'[\s;]+$', '', sql.strip())
    if ';' in _LITERALS_RE.sub(' ', sql):
        raise ApiError('Only a single SQL statement can be executed at a time')
    if not config.allow_writes():
        if first_keyword(sql) not in READ_ONLY_STATEMENTS or '/*!' in sql:
            raise ApiError('Only read-only statements (SELECT, WITH, SHOW, DESCRIBE, EXPLAIN) are allowed. '
                           'Set SQL2API_ALLOW_WRITES=1 to lift this restriction.', 403)
    return sql


def paginate(sql, limit, offset):
    """Replace any trailing LIMIT/OFFSET on a SELECT with the requested window."""
    sql = _TRAILING_LIMIT_RE.sub('', sql)
    return f'{sql}\nLIMIT {int(limit)} OFFSET {int(offset)}'


# --------------------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------------------

def _to_bool(text):
    lowered = text.strip().lower()
    if lowered in ('true', '1', 'yes'):
        return True
    if lowered in ('false', '0', 'no'):
        return False
    raise ValueError(text)


_COERCERS = {'int': int, 'integer': int, 'float': float, 'number': float, 'str': str, 'string': str,
             'bool': _to_bool, 'boolean': _to_bool}


def coerce_params(declared, params):
    """Convert string values (e.g. from a query string) to the types a saved query declares.

    ``declared`` is the saved version's ``query_parameters``: ``{"actor_id": "int"}`` or
    ``{"actor_id": {"type": "int"}}``. Undeclared parameters are left untouched.
    """
    result = dict(params)
    for name, spec in (declared or {}).items():
        type_name = spec.get('type') if isinstance(spec, dict) else spec
        coerce = _COERCERS.get(str(type_name).lower())
        if coerce and isinstance(result.get(name), str):
            try:
                result[name] = coerce(result[name])
            except ValueError:
                raise ApiError(f"Parameter '{name}' must be of type {type_name}") from None
    return result


def _check_value(name, value):
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, (int, float)) and math.isfinite(value):
        return
    raise ApiError(f"Parameter '{name}' must be a string, finite number, boolean or null")


def fill_placeholders(sql, values):
    """Substitute ``{name}`` text placeholders (legacy style; prefer bound ``:name`` parameters).

    Because the value becomes part of the SQL text it is restricted to numbers, booleans and
    plain text so it cannot break out of the query. Only placeholders present in the SQL are
    validated, so the same dict can also carry values for bound parameters.
    """
    for key, value in values.items():
        token = f'{{{key}}}'
        if token not in sql:
            continue
        if isinstance(value, bool):
            text = 'TRUE' if value else 'FALSE'
        elif isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ApiError(f"Placeholder '{key}' must be a finite number")
            text = str(value)
        elif isinstance(value, str) and _SAFE_TEXT_RE.match(value) and '--' not in value:
            text = value
        else:
            raise ApiError(f"Placeholder '{key}' is substituted into the SQL text, so it must be a number, "
                           "boolean or a string containing only letters, digits, whitespace and . , : @ % + / - "
                           f"(use a bound :{key} parameter for arbitrary text)")
        sql = sql.replace(token, text)
    missing = sorted(set(_BRACE_RE.findall(sql)))
    if missing:
        raise ApiError(f"No value provided for placeholder(s): {', '.join(missing)}")
    return sql


def named_parameters(sql):
    """Names of the ``:name`` bound parameters used by ``sql``, in order of appearance."""
    return [m.group('name') for m in _PARAM_RE.finditer(sql) if m.group('name')]


_MARKERS = {'qmark': lambda name: '?', 'format': lambda name: '%s', 'pyformat': lambda name: f'%({name})s'}


def bind_parameters(sql, params, style):
    """Rewrite ``:name`` markers into a driver's paramstyle and return ``(sql, args)``.

    ``style`` is 'qmark' (``?``, positional), 'format' (``%s``, positional) or 'pyformat'
    (``%(name)s``, mapping). Values never become part of the SQL text. Returns ``(sql, None)``
    when the statement has no parameters, so drivers do not apply ``%`` formatting to it.
    """
    matches = [m for m in _PARAM_RE.finditer(sql) if m.group('name')]
    if not matches:
        return sql, None
    names = [m.group('name') for m in matches]
    missing = sorted(set(names) - set(params))
    if missing:
        raise ApiError(f"No value provided for parameter(s): {', '.join(missing)}")
    for name in set(names):
        _check_value(name, params[name])

    escape = (lambda text: text.replace('%', '%%')) if style in ('format', 'pyformat') else (lambda text: text)
    pieces, position = [], 0
    for match in matches:
        pieces.append(escape(sql[position:match.start()]))
        pieces.append(_MARKERS[style](match.group('name')))
        position = match.end()
    pieces.append(escape(sql[position:]))
    args = {name: params[name] for name in names} if style == 'pyformat' else [params[name] for name in names]
    return ''.join(pieces), args
