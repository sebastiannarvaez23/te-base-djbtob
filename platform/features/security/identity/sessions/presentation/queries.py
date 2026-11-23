from core.query import PATTERN_IP, PATTERN_TEXT, QueryFilter, QueryParam


class SessionsQuery(QueryFilter):
    username   = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    company    = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    ip_address = QueryParam(coerce=str, max_length=45, pattern=PATTERN_IP)
    status     = QueryParam(coerce=str, choices=['active', 'inactive'])
