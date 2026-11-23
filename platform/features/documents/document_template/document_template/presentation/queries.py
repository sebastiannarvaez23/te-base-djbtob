from core.query import (
    PATTERN_CODE,
    PATTERN_CODE_UPPER,
    PATTERN_TEXT,
    QueryFilter,
    QueryParam,
)


class DocumentTemplateListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    kind = QueryParam(coerce=str, max_length=40, pattern=PATTERN_CODE_UPPER)
    is_active = QueryParam(coerce=bool)
    is_storable = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class DocumentGeneratedListQuery(QueryFilter):
    limit = QueryParam(coerce=int, min_value=1, max_value=200)
    offset = QueryParam(coerce=int, min_value=0)
