from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class CountryListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    code = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)


class DepartmentListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    country_id = QueryParam(coerce=str, is_uuid=True)
    country_code = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')
    is_active = QueryParam(coerce=bool)


class CityListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    department_id = QueryParam(coerce=str, is_uuid=True)
    country_id = QueryParam(coerce=str, is_uuid=True)
    country_code = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')
    is_active = QueryParam(coerce=bool)
