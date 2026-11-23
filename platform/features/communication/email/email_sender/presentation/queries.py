from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class EmailSenderListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    email = QueryParam(coerce=str, is_email=True)
    is_active = QueryParam(coerce=bool)
    is_default = QueryParam(coerce=bool)
