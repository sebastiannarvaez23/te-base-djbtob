from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class CompanyQuery(QueryFilter):
    name         = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    nit          = QueryParam(coerce=str, max_length=40, pattern=PATTERN_CODE)
    city         = QueryParam(coerce=str, max_length=255, pattern=PATTERN_TEXT)
    subscription = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status       = QueryParam(coerce=str, choices=['active', 'inactive'])
    lifecycle    = QueryParam(coerce=str, choices=['ACTIVE', 'CLOSED', 'PENDING_PURGE'])
