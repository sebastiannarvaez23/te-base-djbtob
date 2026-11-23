from core.query import PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam


class SubscriptionFunctionalityBySubscriptionQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    functionality_key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
