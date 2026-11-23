import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

RefundStatus = Literal['pending', 'accepted', 'processing', 'completed', 'failed', 'rejected']
RefundKind = Literal['full', 'difference']


class PeriodSnapshot(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_name: str
    start_date: datetime
    price_paid: Decimal
    billing_interval: str
    status: str


class RefundableCharge(BaseModel):
    id: uuid.UUID
    amount: Decimal
    refunded_amount: Decimal
    currency: str
    status: str

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.refunded_amount


class CreateRefundTicketSchema(BaseModel):
    company_id: uuid.UUID
    schema_name: str
    ticket_number: str
    from_subscription_id: uuid.UUID
    from_subscription_name: str
    to_subscription_id: uuid.UUID
    to_subscription_name: str
    period_id: uuid.UUID
    charge_id: uuid.UUID
    amount: Decimal
    currency: str
    kind: RefundKind
    payout_due_on: date
    charge_refunded_before: Decimal
    requested_by_id: Optional[uuid.UUID] = None


class RefundTicketSchema(BaseModel):
    id: uuid.UUID
    ticket_number: str
    company_id: uuid.UUID
    schema_name: str
    from_subscription_id: uuid.UUID
    from_subscription_name: str
    to_subscription_id: uuid.UUID
    to_subscription_name: str
    period_id: uuid.UUID
    charge_id: uuid.UUID
    amount: Decimal
    currency: str
    kind: RefundKind
    status: RefundStatus
    payout_due_on: date
    charge_refunded_before: Decimal
    gateway_refund_id: str = ''
    failure_message: str = ''
    rejection_reason: str = ''
    requested_by_id: Optional[uuid.UUID] = None
    approved_by_id: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class PayoutResult(BaseModel):
    ok: bool
    refunded_amount: Decimal = Decimal('0')
    gateway_refund_id: str = ''
    error: str = ''


class RefundEligibilitySchema(BaseModel):
    eligible: bool
    reason_code: Optional[str] = None
    window_ends_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    current_plan_id: Optional[uuid.UUID] = None
    current_plan_name: Optional[str] = None
    price_paid: Decimal = Decimal('0')
    billing_interval: str = 'monthly'
    sla_business_days: int = 30
    cooldown_days: int = 90
    open_ticket: Optional[RefundTicketSchema] = None


class RefundPreviewSchema(BaseModel):
    eligibility: RefundEligibilitySchema
    target_plan_id: uuid.UUID
    target_plan_name: str
    target_amount: Decimal
    refund_amount: Decimal
    refund_kind: RefundKind
    currency: str
    payout_due_on: date
    switches_immediately: bool = False
    cooldown_after_days: int = 90


class AdminRefundTicketSchema(RefundTicketSchema):
    company_name: str = ''
    company_nit: str = ''


class RefundNotification(BaseModel):
    schema_name: str
    ticket_id: uuid.UUID
    ticket_number: str
    status: RefundStatus
    title: str = Field(min_length=1, max_length=200)
    body: str
    level: Literal['INFO', 'SUCCESS', 'WARNING'] = 'INFO'
