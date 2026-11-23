from core.query import PATTERN_KEY, PATTERN_TEXT, QueryFilter, QueryParam


class ComplementCatalogQuery(QueryFilter):
    label = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    billing_mode = QueryParam(coerce=str, choices=['renewal', 'one_time'])


class CompanyComplementQuery(QueryFilter):
    status = QueryParam(coerce=str, choices=['active', 'revoked', 'expired'])
    key = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
