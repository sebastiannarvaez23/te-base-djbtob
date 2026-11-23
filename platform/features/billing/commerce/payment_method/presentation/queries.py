from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class PaymentMethodListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    is_active = QueryParam(coerce=bool)
    provider = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
