from core.query import PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam


class ConnectionRelatedQuery(QueryFilter):
    connection_id = QueryParam(coerce=str, is_uuid=True)


class ConnectionListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(
        coerce=str,
        choices=['ACTIVE', 'PAUSED', 'DEGRADED', 'ERROR'],
    )
    environment = QueryParam(
        coerce=str,
        choices=['PROSANDBOX', 'CLIENT_TEST', 'CLIENT_PROD'],
    )
    connector_key = QueryParam(coerce=str, max_length=50, pattern=PATTERN_KEY)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
