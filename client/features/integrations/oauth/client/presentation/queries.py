from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class IntegrationApplicationListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(coerce=str, choices=['ACTIVE', 'DISABLED', 'REVOKED'])
    environment = QueryParam(coerce=str, choices=['CLIENT_TEST', 'CLIENT_PROD'])
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
