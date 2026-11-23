from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class EmailTemplateListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    sender_id = QueryParam(coerce=str, is_uuid=True)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
