from core.query import PATTERN_CODE, PATTERN_CODE_UPPER_KEBAB, PATTERN_TEXT, QueryFilter, QueryParam


class PolicyListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    code = QueryParam(coerce=str, max_length=80, pattern=PATTERN_CODE_UPPER_KEBAB)
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    audience = QueryParam(coerce=str, max_length=16, choices=['client', 'admin'])
    is_active = QueryParam(coerce=bool)
    country = QueryParam(
        coerce=str,
        max_length=64,
        pattern=r'^[A-Za-z]{2}(,[A-Za-z]{2})*$',
    )
    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)


class PendingPoliciesQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    country = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')


class PolicySignaturesQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    country = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')
    subject_id = QueryParam(coerce=str, max_length=64, pattern=PATTERN_CODE)
    subject_type = QueryParam(coerce=str, max_length=16, choices=['client', 'admin'])


class PolicyCountryContentQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    status = QueryParam(
        coerce=str,
        max_length=16,
        choices=['draft', 'published'],
    )
