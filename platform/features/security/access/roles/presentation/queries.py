from core.query import PATTERN_CODE, PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam
from platform.features.security.access.functionalities.domain.categories import FUNCTIONALITY_CATEGORIES


class CatalogListQuery(QueryFilter):
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 200

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    label = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    module_id = QueryParam(coerce=str, is_uuid=True)


class CatalogFeatureListQuery(CatalogListQuery):
    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    category = QueryParam(coerce=str, choices=list(FUNCTIONALITY_CATEGORIES))


class SectionListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class AdminRoleListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class AdminModulesCatalogQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class AdminFeaturesCatalogQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    is_active = QueryParam(coerce=bool)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
