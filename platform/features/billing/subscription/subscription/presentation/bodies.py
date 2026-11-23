from decimal import Decimal

from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateSubscriptionBody(RequestBody):
    name = Field(str, min_length=1, max_length=200, pattern=PATTERN_CONTENT)
    price = Field(Decimal, min_value=0)
    currency = Field(str, required=False, max_length=3, pattern=r'^([A-Za-z]{3})?$', default='USD')
    code = Field(str, min_length=1, max_length=50, pattern=PATTERN_CODE)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    logo = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    is_active = Field(bool, required=False, default=True)


class UpdateSubscriptionBody(RequestBody):
    name = Field(str, required=False, min_length=1, max_length=200, pattern=PATTERN_CONTENT)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    logo = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    is_active = Field(bool, required=False)
    catalog_service_id = Field(str, required=False, nullable=True, is_uuid=True)


class UpgradeSubscriptionBody(RequestBody):
    subscription_id = Field(str, required=True, is_uuid=True)
    payment_method_id = Field(str, required=False, nullable=True, is_uuid=True)
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'])


class RetryPaymentBody(RequestBody):
    payment_method_id = Field(str, required=False, nullable=True, is_uuid=True)


class UpdateAnnualDiscountBody(RequestBody):
    annual_discount_percent = Field(Decimal, min_value=0, max_value=100)
