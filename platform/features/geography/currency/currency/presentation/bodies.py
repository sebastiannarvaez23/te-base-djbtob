from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_CURRENCY = r'^[A-Za-z]{3}$'


class CreateCurrencyBody(RequestBody):
    code = Field(str, max_length=3, pattern=_CURRENCY)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    decimal_places = Field(int, required=False, default=2, min_value=0, max_value=6)
    is_active = Field(bool, required=False, default=True)


class UpdateCurrencyBody(RequestBody):
    name = Field(str, required=False, max_length=120, pattern=PATTERN_CONTENT)
    decimal_places = Field(int, required=False, min_value=0, max_value=6)
    is_active = Field(bool, required=False)


class CreateCountryCurrencyBody(RequestBody):
    currency_id = Field(str, is_uuid=True)
    is_default = Field(bool, required=False, default=False)
    is_active = Field(bool, required=False, default=True)


class UpdateCountryCurrencyBody(RequestBody):
    is_default = Field(bool, required=False)
    is_active = Field(bool, required=False)
