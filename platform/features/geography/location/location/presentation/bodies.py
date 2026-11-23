from decimal import Decimal

from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_COUNTRY = r'^[A-Za-z]{2}$'
_LOC_CODE = r'^[A-Za-z0-9][A-Za-z0-9\-_]{0,19}$'


class CreateCountryBody(RequestBody):
    code = Field(str, max_length=2, pattern=_COUNTRY)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False, default=None)
    longitude = Field(Decimal, required=False, default=None)
    is_active = Field(bool, required=False, default=True)


class UpdateCountryBody(RequestBody):
    name = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False)
    longitude = Field(Decimal, required=False)
    is_active = Field(bool, required=False)


class CreateDepartmentBody(RequestBody):
    country_id = Field(str, is_uuid=True)
    code = Field(str, max_length=20, pattern=_LOC_CODE)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False, default=None)
    longitude = Field(Decimal, required=False, default=None)
    is_active = Field(bool, required=False, default=True)


class UpdateDepartmentBody(RequestBody):
    name = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False)
    longitude = Field(Decimal, required=False)
    is_active = Field(bool, required=False)


class CreateCityBody(RequestBody):
    department_id = Field(str, is_uuid=True)
    code = Field(str, max_length=20, pattern=_LOC_CODE)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False, default=None)
    longitude = Field(Decimal, required=False, default=None)
    is_active = Field(bool, required=False, default=True)


class UpdateCityBody(RequestBody):
    name = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    latitude = Field(Decimal, required=False)
    longitude = Field(Decimal, required=False)
    is_active = Field(bool, required=False)
