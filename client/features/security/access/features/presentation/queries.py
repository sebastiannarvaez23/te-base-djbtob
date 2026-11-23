from core.query import PATTERN_KEY, QueryFilter, QueryParam


class FeatureListQuery(QueryFilter):
    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
