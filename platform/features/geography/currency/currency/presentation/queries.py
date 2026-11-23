from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class CurrencyListQuery(QueryFilter):
    """Small Redis-cached catalog — unpaginated dump is intentional."""

    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    code = QueryParam(coerce=str, max_length=3, pattern=r'^[A-Za-z]{3}$')
    is_active = QueryParam(coerce=bool)


class CountryCurrencyListQuery(QueryFilter):
    """Country↔currency links — unpaginated dump is intentional for admin pickers."""

    ALLOW_UNPAGINATED = True

    is_active = QueryParam(coerce=bool)
    is_default = QueryParam(coerce=bool)
    currency_code = QueryParam(coerce=str, max_length=3, pattern=r'^[A-Za-z]{3}$')


class AllowedCurrencyQuery(QueryFilter):
    """Allowed currencies for one country — always a short list."""

    ALLOW_UNPAGINATED = True

    country_code = QueryParam(coerce=str, required=True, max_length=2, pattern=r'^[A-Za-z]{2}$')
