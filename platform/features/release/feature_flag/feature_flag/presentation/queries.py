from core.query import PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam


class FeatureFlagListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(
        coerce=str,
        choices=['DRAFT', 'ACTIVE', 'CERTIFIED', 'DISABLED', 'ARCHIVED'],
    )
    flag_type = QueryParam(coerce=str, choices=['RELEASE', 'OPS'])
    enabled = QueryParam(coerce=bool)
    owner = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
