from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class AdminUsersQuery(QueryFilter):
    name     = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    email    = QueryParam(coerce=str, is_email=True)
    username = QueryParam(coerce=str, max_length=150, pattern=PATTERN_TEXT)
    role     = QueryParam(coerce=str, max_length=100, pattern=PATTERN_TEXT)
    status   = QueryParam(coerce=str, choices=['active', 'inactive'])
