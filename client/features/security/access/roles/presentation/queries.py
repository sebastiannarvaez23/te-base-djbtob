from core.query import PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam


class RolesListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class FeaturesCatalogQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    key = QueryParam(coerce=str, max_length=200, pattern=PATTERN_KEY)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class GenericRolesListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
