import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateVoucherSchema(BaseModel):
    voucher_type: str
    scope: str
    company_id: Optional[uuid.UUID] = None
    subscription_ids: list[uuid.UUID] = Field(min_length=1)
    discount_percent: Optional[Decimal] = None
    benefit_months: Optional[int] = None
    discount_duration_months: int = 1
    redeem_valid_from: datetime
    redeem_valid_until: datetime
    notes: str = ''
    created_by_id: Optional[uuid.UUID] = None


class CreateBulkVouchersSchema(BaseModel):
    voucher_type: str
    scope: str = 'COMPANY'
    company_ids: list[uuid.UUID] = Field(default_factory=list)
    all_companies: bool = False
    subscription_ids: list[uuid.UUID] = Field(min_length=1)
    discount_percent: Optional[Decimal] = None
    benefit_months: Optional[int] = None
    discount_duration_months: int = 1
    redeem_valid_from: datetime
    redeem_valid_until: datetime
    notes: str = ''
    created_by_id: Optional[uuid.UUID] = None


class ValidateVoucherSchema(BaseModel):
    serial: str
    subscription_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    context: str = 'SETTINGS'
    billing_interval: Optional[str] = None


class RedeemVoucherSchema(BaseModel):
    serial: str
    subscription_id: uuid.UUID
    company_id: uuid.UUID
    context: str = 'SETTINGS'
    idempotency_key: Optional[str] = None
    payment_method_id: Optional[uuid.UUID] = None
    billing_interval: Optional[str] = None


class ApplyOnboardingVoucherSchema(BaseModel):
    serial: str
    subscription_id: uuid.UUID
    billing_interval: Optional[str] = None


class VoucherSubscriptionSchema(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    code: str


class AdminSnapshot(BaseModel):
    """ORM-free view of a company's admin user for the directory port."""
    email: str
    first_name: str = ''
    last_name: str = ''


class VoucherPreviewSchema(BaseModel):
    serial: str
    voucher_type: str
    subscription_id: uuid.UUID
    subscription_name: str
    original_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal
    benefit_months: Optional[int] = None
    discount_percent: Optional[Decimal] = None
    discount_duration_months: Optional[int] = None
    redeem_valid_until: datetime
    message: str = ''


class VoucherSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    serial: str
    voucher_type: str
    scope: str
    origin: str
    status: str
    company_id: Optional[uuid.UUID] = None
    company_name: Optional[str] = None
    discount_percent: Optional[Decimal] = None
    benefit_months: Optional[int] = None
    discount_duration_months: int = 1
    redeem_valid_from: datetime
    redeem_valid_until: datetime
    subscription_ids: list[uuid.UUID] = Field(default_factory=list)
    subscription_names: list[str] = Field(default_factory=list)
    subscription_prices: list[Decimal] = Field(default_factory=list)
    notes: str = ''
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class RedemptionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voucher_id: uuid.UUID
    voucher_serial: str
    company_id: uuid.UUID
    company_name: str
    redeemed_at: datetime
    context: str
    subscription_id: uuid.UUID
    subscription_name: str
    original_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal


class BulkCreateResultSchema(BaseModel):
    created: int
    failed: list[dict] = Field(default_factory=list)
    vouchers: list[VoucherSchema] = Field(default_factory=list)


class RedeemResultSchema(BaseModel):
    redemption: RedemptionSchema
    preview: VoucherPreviewSchema
    benefit_id: Optional[uuid.UUID] = None
    previous_plan_id: Optional[uuid.UUID] = None


class ActiveBenefitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voucher_type: str
    voucher_serial: str
    subscription_id: uuid.UUID
    subscription_name: str
    benefit_start: datetime
    benefit_end: datetime
    benefit_months: Optional[int] = None
    discount_percent: Optional[Decimal] = None
    remaining_discount_cycles: Optional[int] = None
    discount_duration_months: Optional[int] = None
    status: str
    company_id: Optional[uuid.UUID] = None
    previous_subscription_id: Optional[uuid.UUID] = None
    voucher_id: Optional[uuid.UUID] = None


class PlanSnapshot(BaseModel):
    """Immutable, ORM-free view of a subscription plan used by domain services."""

    id: uuid.UUID
    name: str
    code: str = ''
    price: Decimal


class CreateRedemptionSchema(BaseModel):
    voucher_id: uuid.UUID
    company_id: uuid.UUID
    context: str
    subscription_id: uuid.UUID
    original_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal
    idempotency_key: Optional[str] = None


class CreateBenefitSchema(BaseModel):
    company_id: uuid.UUID
    redemption_id: Optional[uuid.UUID] = None
    voucher_type: str
    subscription_id: uuid.UUID
    previous_subscription_id: Optional[uuid.UUID] = None
    benefit_start: datetime
    benefit_end: datetime
    discount_percent: Optional[Decimal] = None
    remaining_discount_cycles: Optional[int] = None


class RenewalChargeDecision(BaseModel):
    amount: Decimal
    metadata: dict = Field(default_factory=dict)
    skip_charge: bool = False


class ChargeSnapshot(BaseModel):
    id: Optional[uuid.UUID] = None
    status: str
    failure_message: str = ''

    @property
    def is_captured(self) -> bool:
        return str(self.status).lower() == 'captured'


class PublicPurchasePreviewRequestSchema(BaseModel):
    voucher_type: str
    subscription_id: uuid.UUID
    benefit_months: Optional[int] = None
    discount_percent: Optional[Decimal] = None
    discount_duration_months: Optional[int] = None


class PublicPurchasePreviewResponseSchema(BaseModel):
    amount: Decimal
    currency: str = 'USD'
    description: str


class PublicPurchaseBuyerSchema(BaseModel):
    name: str
    email: str
    phone: str = ''
    country: str = ''


class PublicPurchaseRecipientSchema(BaseModel):
    name: str
    email: str
    message: str = ''
    company_name: str = ''


class PublicPurchasePaymentSchema(BaseModel):
    processor_token: str
    holder: str
    last4: str
    expiry_month: int
    expiry_year: int
    card_number: str = ''


class PublicPurchaseCheckoutSchema(BaseModel):
    voucher_type: str
    subscription_id: uuid.UUID
    benefit_months: Optional[int] = None
    discount_percent: Optional[Decimal] = None
    discount_duration_months: Optional[int] = None
    buyer: PublicPurchaseBuyerSchema
    recipient: PublicPurchaseRecipientSchema
    payment: PublicPurchasePaymentSchema
    idempotency_key: str


class PublicPurchaseCheckoutResultSchema(BaseModel):
    voucher_serial: str
    redeem_valid_until: datetime
    amount_paid: Decimal
    charge_id: Optional[uuid.UUID] = None
