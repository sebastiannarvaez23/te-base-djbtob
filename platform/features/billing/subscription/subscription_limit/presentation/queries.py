from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class SubscriptionLimitListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    subscription_id = QueryParam(coerce=str, is_uuid=True)
    functionality_id = QueryParam(coerce=str, is_uuid=True)
    validation_type = QueryParam(coerce=str, choices=['daily', 'lifetime', 'window'])
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class SubscriptionLimitBySubscriptionQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    functionality_id = QueryParam(coerce=str, is_uuid=True)
    validation_type = QueryParam(coerce=str, choices=['daily', 'lifetime', 'window'])
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
