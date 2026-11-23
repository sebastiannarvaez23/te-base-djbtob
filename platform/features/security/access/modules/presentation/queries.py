from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class ModuleQuery(QueryFilter):
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    code = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    section_id = QueryParam(coerce=str, is_uuid=True)
    is_active = QueryParam(coerce=bool)


class ModuleCatalogQuery(ModuleQuery):
    """Catalog list: unpaginated by default; admin ModuleQuery stays paginated."""

    ALLOW_UNPAGINATED = True
