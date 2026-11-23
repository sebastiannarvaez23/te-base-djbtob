from decimal import Decimal

from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT, PATTERN_PHONE


class CreateVoucherBody(RequestBody):
    voucher_type = Field(str, choices=['GIFT', 'DISCOUNT'])
    scope = Field(str, choices=['COMPANY', 'OPEN', 'FIRST_TAKE'])
    company_id = Field(str, required=False, nullable=True, is_uuid=True)
    subscription_ids = Field(list, min_items=1)
    discount_percent = Field(Decimal, required=False, nullable=True)
    benefit_months = Field(int, required=False, nullable=True, min_value=1, max_value=36)
    discount_duration_months = Field(int, required=False, min_value=1, default=1)
    redeem_valid_from = Field(str, max_length=5000, pattern=PATTERN_CONTENT)
    redeem_valid_until = Field(str, max_length=5000, pattern=PATTERN_CONTENT)
    notes = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')


class CreateBulkVouchersBody(RequestBody):
    voucher_type = Field(str, choices=['GIFT', 'DISCOUNT'])
    company_ids = Field(list, required=False, default=list)
    all_companies = Field(bool, required=False, default=False)
    subscription_ids = Field(list, min_items=1)
    discount_percent = Field(Decimal, required=False, nullable=True)
    benefit_months = Field(int, required=False, nullable=True, min_value=1, max_value=36)
    discount_duration_months = Field(int, required=False, min_value=1, default=1)
    redeem_valid_from = Field(str, max_length=5000, pattern=PATTERN_CONTENT)
    redeem_valid_until = Field(str, max_length=5000, pattern=PATTERN_CONTENT)
    notes = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')


class ValidateVoucherBody(RequestBody):
    serial = Field(str, max_length=32, pattern=PATTERN_CONTENT)
    subscription_id = Field(str, is_uuid=True)
    company_id = Field(str, required=False, nullable=True, is_uuid=True)
    context = Field(
        str, required=False,
        choices=['ONBOARDING', 'SETTINGS', 'PUBLIC_PURCHASE'],
        default='SETTINGS',
    )
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'])


class RedeemVoucherBody(RequestBody):
    serial = Field(str, max_length=32, pattern=PATTERN_CONTENT)
    subscription_id = Field(str, is_uuid=True)
    idempotency_key = Field(str, required=False, nullable=True, max_length=64, pattern=PATTERN_CODE)
    payment_method_id = Field(str, required=False, nullable=True, is_uuid=True)
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'])


class ApplyOnboardingVoucherBody(RequestBody):
    serial = Field(str, max_length=32, pattern=PATTERN_CONTENT)
    subscription_id = Field(str, is_uuid=True)
    billing_interval = Field(str, required=False, choices=['monthly', 'yearly'])


class PublicPurchaseBuyerBody(RequestBody):
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    email = Field(str, is_email=True)
    phone = Field(str, required=False, max_length=32, default='', pattern=PATTERN_PHONE)
    country = Field(str, required=False, max_length=64, default='', pattern=PATTERN_CONTENT)


class PublicPurchaseRecipientBody(RequestBody):
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    email = Field(str, is_email=True)
    message = Field(str, required=False, max_length=500, default='', pattern=PATTERN_CONTENT)
    company_name = Field(str, required=False, max_length=120, default='', pattern=PATTERN_CONTENT)


class PublicPurchasePaymentBody(RequestBody):
    processor_token = Field(str, min_length=8, max_length=512, pattern=PATTERN_CONTENT)
    holder = Field(str, max_length=80, pattern=PATTERN_CONTENT)
    last4 = Field(str, min_length=4, max_length=4, pattern=PATTERN_CONTENT)
    expiry_month = Field(int, min_value=1, max_value=12)
    expiry_year = Field(int, min_value=2020, max_value=2100)
    card_number = Field(str, required=False, max_length=19, default='', pattern=PATTERN_CONTENT)


class PublicPurchasePreviewBody(RequestBody):
    voucher_type = Field(str, choices=['GIFT', 'DISCOUNT'])
    subscription_id = Field(str, is_uuid=True)
    benefit_months = Field(int, required=False, nullable=True, min_value=1, max_value=36)
    discount_percent = Field(Decimal, required=False, nullable=True)
    discount_duration_months = Field(int, required=False, nullable=True, min_value=1)


class PublicPurchaseCheckoutBody(RequestBody):
    voucher_type = Field(str, choices=['GIFT', 'DISCOUNT'])
    subscription_id = Field(str, is_uuid=True)
    benefit_months = Field(int, required=False, nullable=True, min_value=1, max_value=36)
    discount_percent = Field(Decimal, required=False, nullable=True)
    discount_duration_months = Field(int, required=False, nullable=True, min_value=1)
    buyer = Field(dict, schema=PublicPurchaseBuyerBody)
    recipient = Field(dict, schema=PublicPurchaseRecipientBody)
    payment = Field(dict, schema=PublicPurchasePaymentBody)
    idempotency_key = Field(str, min_length=8, max_length=64, pattern=PATTERN_CODE)
