from core.query import PATTERN_CODE, QueryFilter, QueryParam


class LandingSectionListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    is_visible = QueryParam(coerce=bool)
