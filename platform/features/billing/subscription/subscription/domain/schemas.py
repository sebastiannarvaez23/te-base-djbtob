import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, computed_field, field_validator

from .billing_cycle import DEFAULT_ANNUAL_DISCOUNT_PERCENT, yearly_amount


PeriodStatus = Literal['active', 'closed', 'cancelled', 'expired', 'suspended']


def _normalize_currency(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if len(cleaned) != 3 or not cleaned.isalpha():
        raise ValueError('currency must be ISO 4217 alpha-3 (e.g. USD)')
    return cleaned


class SubscriptionSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    name: str
    price: Decimal
    currency: str = 'USD'
    code: str
    description: str = ''
    logo: str = ''
    modules: List[str] = []
    features: List[str] = []
    is_active: bool
    catalog_service_id: Optional[uuid.UUID] = None
    catalog_service_code: str = ''
    catalog_service_name: str = ''
    annual_discount_percent: Decimal = DEFAULT_ANNUAL_DISCOUNT_PERCENT
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator('currency', mode='before')
    @classmethod
    def _currency(cls, value) -> str:
        return _normalize_currency(str(value or 'USD'))

    @computed_field
    @property
    def yearly_price(self) -> Decimal:
        return yearly_amount(self.price, self.annual_discount_percent)


class BillingSettingsSchema(BaseModel):
    annual_discount_percent: Decimal


class CreateSubscriptionSchema(BaseModel):
    name: str
    price: Decimal
    currency: str = 'USD'
    code: str
    description: str = ''
    logo: str = ''
    is_active: bool = True

    @field_validator('currency', mode='before')
    @classmethod
    def _currency(cls, value) -> str:
        return _normalize_currency(str(value or 'USD'))


class UpdateSubscriptionSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    is_active: Optional[bool] = None
    catalog_service_id: Optional[uuid.UUID] = None
    catalog_service_code: Optional[str] = None
    catalog_service_name: Optional[str] = None
    # Written only after resolving the linked Neurana service. The HTTP body
    # does not accept these fields.
    price: Optional[Decimal] = None
    currency: Optional[str] = None

    @field_validator('currency', mode='before')
    @classmethod
    def _currency(cls, value):
        if value is None or value == '':
            return None
        return _normalize_currency(str(value))


class CompanySubscriptionResultSchema(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_name: str
    start_date: datetime
    ends_at: datetime
    status: PeriodStatus
    billing_interval: str = 'monthly'

    @field_validator('status', mode='before')
    @classmethod
    def _normalize_status(cls, value):
        return value.lower() if isinstance(value, str) else value

    @computed_field
    @property
    def end_date(self) -> str:
        """Display label for existing settings clients (`dd/mm/YYYY`)."""
        return self.ends_at.strftime('%d/%m/%Y')


class ActivePeriodSchema(BaseModel):
    """Live billing period of a company (no presentation formatting)."""

    id: uuid.UUID
    subscription_id: uuid.UUID
    status: PeriodStatus = 'active'


class PendingChangeSchema(BaseModel):
    type: Literal['downgrade']
    from_plan: str
    to_plan: str
    activates_on: datetime
    billing_interval: str = 'monthly'


class PendingDowngradeDueSchema(BaseModel):
    company_id: uuid.UUID
    pending_subscription_id: uuid.UUID


class RetrySuspendedPaymentInputSchema(BaseModel):
    company_id: uuid.UUID
    payment_method_id: Optional[uuid.UUID] = None
    access_mode: Literal['full', 'billing_recovery'] = 'full'
