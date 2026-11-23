from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class TenantUsersQuery(QueryFilter):
    name    = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    email   = QueryParam(coerce=str, is_email=True)
    company = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status  = QueryParam(coerce=str, choices=['active', 'inactive'])
