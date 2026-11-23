from decimal import Decimal

from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateChargeBody(RequestBody):
    amount = Field(Decimal, min_value=0)
    currency = Field(str, required=False, max_length=3, pattern=r'^([A-Za-z]{3})?$', default='')
    method_type = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='card')
    description = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    invoice_id = Field(str, required=False, nullable=True, is_uuid=True)
    payment_method_id = Field(str, required=False, nullable=True, is_uuid=True)
    idempotency_key = Field(str, required=False, max_length=128, default='', pattern=PATTERN_CODE)
    gateway_payment_method_id = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    return_url = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    cancel_url = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    metadata = Field(dict, required=False, default=dict)
    card_number = Field(str, required=False, max_length=24, default='', pattern=PATTERN_CONTENT)
    card_exp_month = Field(int, required=False, nullable=True, min_value=1, max_value=12)
    card_exp_year = Field(int, required=False, nullable=True, min_value=2000)
    card_cvc = Field(str, required=False, max_length=4, default='', pattern=PATTERN_CONTENT)
    card_holder = Field(str, required=False, max_length=200, default='', pattern=PATTERN_CONTENT)


class ConfirmChargeBody(RequestBody):
    payload = Field(dict, required=False, default=dict)


class CaptureChargeBody(RequestBody):
    amount = Field(Decimal, required=False, nullable=True, min_value=0)


class CancelChargeBody(RequestBody):
    reason = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)


class RefundChargeBody(RequestBody):
    amount = Field(Decimal, required=False, nullable=True, min_value=0)
    reason = Field(str, required=False, max_length=255, default='', pattern=PATTERN_CONTENT)
    currency = Field(str, required=False, max_length=3, pattern=r'^([A-Za-z]{3})?$', default='')
