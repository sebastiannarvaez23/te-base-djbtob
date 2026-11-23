from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreatePaymentMethodBody(RequestBody):
    name = Field(str, required=True, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    provider = Field(str, required=True, min_length=2, max_length=100, pattern=PATTERN_CODE)
    holder = Field(str, required=True, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    last4 = Field(str, required=True, min_length=4, max_length=4, pattern=PATTERN_CONTENT)
    expiry = Field(str, required=True, min_length=5, max_length=5, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class UpdatePaymentMethodBody(RequestBody):
    name = Field(str, required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    provider = Field(str, required=False, min_length=2, max_length=100, pattern=PATTERN_CODE)
    holder = Field(str, required=False, min_length=2, max_length=200, pattern=PATTERN_CONTENT)
    last4 = Field(str, required=False, min_length=4, max_length=4, pattern=PATTERN_CONTENT)
    expiry = Field(str, required=False, min_length=5, max_length=5, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False)
