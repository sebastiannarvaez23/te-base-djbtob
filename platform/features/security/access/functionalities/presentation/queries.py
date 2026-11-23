from core.query import PATTERN_CODE, PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam
from platform.features.security.access.functionalities.domain.categories import FUNCTIONALITY_CATEGORIES
from platform.features.security.access.functionalities.domain.offering import BILLING_MODES, OFFERINGS


class FunctionalityQuery(QueryFilter):
    label = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    category = QueryParam(coerce=str, choices=list(FUNCTIONALITY_CATEGORIES))
    offering = QueryParam(coerce=str, choices=list(OFFERINGS))
    billing_mode = QueryParam(coerce=str, choices=list(BILLING_MODES))
    is_active = QueryParam(coerce=bool)
