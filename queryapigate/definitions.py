"""Validation of a saved-query definition - shared by everything that creates one (``PATCH /save_sql_to_file``
and ``queryapigate collection import``), so a query is held to the same rules however it arrives."""
from . import params as param_rules
from . import sqltools, store
from .errors import ApiError

NO_COLLECTION_GIVEN = store._UNSET  # the request said nothing about a collection: leave the query's as it is


def as_object(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ApiError(f'{label} must be a JSON object')
    return value


def validate_definition(data):
    """Check ``data`` (a decoded request body or bundle entry) and return ``(fields, collection)``: the fields
    to store on the new version, and the collection to file the query under - ``NO_COLLECTION_GIVEN`` when
    ``data`` has no ``collection`` key, None to remove it from any, or a valid collection name."""
    for field, label in (('author', 'Author'), ('description', 'Description'),
                         ('sql_query', 'SQL query'), ('filename', 'Filename')):
        if not data.get(field) or not isinstance(data[field], str):
            raise ApiError(f'{label} is missing')
    tags = data.get('tags', [])
    if not isinstance(tags, (list, str)):
        raise ApiError('tags must be a string or a list')
    query_parameters = as_object(data.get('query_parameters'), 'query_parameters')
    param_rules.parse_definitions(query_parameters)
    unused = sorted(set(query_parameters) - set(sqltools.placeholder_names(data['sql_query'])))
    if unused:
        raise ApiError(f"query_parameters declares {', '.join(unused)}, which sql_query does not use "
                       '(write :name in the SQL, or remove the declaration)')
    connection_name = data.get('connection_name')
    if connection_name is not None and not isinstance(connection_name, str):
        raise ApiError('connection_name must be a string')
    cache_ttl = data.get('cache_ttl')
    if cache_ttl is not None and (not isinstance(cache_ttl, int) or isinstance(cache_ttl, bool) or cache_ttl < 0):
        raise ApiError('cache_ttl must be a non-negative integer number of seconds')
    collection = NO_COLLECTION_GIVEN
    if 'collection' in data:
        collection = data['collection']
        if collection is not None:
            store.validate_collection_name(collection)

    fields = {
        'sql_query': data['sql_query'],
        'author': data['author'],
        'description': data['description'],
        'tags': tags,
        'query_parameters': query_parameters,
        **({'connection_name': connection_name} if connection_name else {}),
        **({'cache_ttl': cache_ttl} if cache_ttl else {}),
    }
    return fields, collection


def effective_parameters(saved):
    """A saved version's parameters as callers must supply them: every placeholder its SQL actually uses, in the
    order it uses them, with the declared rules (an undeclared one is plain required text). The one place this is
    derived - the OpenAPI document, the catalogue and the Postman export all describe a query's parameters, and
    must not each work them out separately."""
    declared = param_rules.read_definitions(saved.get('query_parameters'))
    return {name: declared.get(name) or param_rules.read_definition({})
            for name in sqltools.placeholder_names(saved['sql_query'])}
