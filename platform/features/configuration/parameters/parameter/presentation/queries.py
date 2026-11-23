from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class ParameterListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    data_type = QueryParam(
        coerce=str,
        choices=['STRING', 'INT', 'DECIMAL', 'BOOL', 'JSON'],
    )
    parameter_type_id = QueryParam(coerce=str, is_uuid=True)
    is_active = QueryParam(coerce=bool)
