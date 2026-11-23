from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class SubscriptionModuleBySubscriptionQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    module_code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
