from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class CompanyUsersQuery(QueryFilter):
    """
    Query filter for GET /users.

    All params are optional — omitting one means no filter is applied for that field.

    Params
    ------
    q          : One box for name, username, or email (case-insensitive, OR).
    name       : Partial match on first_name or last_name (case-insensitive).
    email      : Partial match on email (case-insensitive).
    username   : Partial match on username (case-insensitive).
    role       : Partial match on rol name (case-insensitive).
    status     : Exact filter. Accepted values: 'active', 'inactive'.
    """
    q        = QueryParam(coerce=str, max_length=100, pattern=PATTERN_TEXT)
    name     = QueryParam(coerce=str, max_length=100, pattern=PATTERN_TEXT)
    email    = QueryParam(coerce=str, is_email=True)
    username = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    role     = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status   = QueryParam(coerce=str, choices=['active', 'inactive'])
