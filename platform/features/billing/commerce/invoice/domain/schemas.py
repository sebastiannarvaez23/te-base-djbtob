import uuid
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime


InvoiceStatusType = Literal['pending', 'paid', 'cancelled', 'overdue']


class InvoiceSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    invoice_number: str
    company_id: uuid.UUID
    subscription_id: uuid.UUID
    company_subscription_id: Optional[uuid.UUID] = None
    source_charge_id: Optional[uuid.UUID] = None
    issue_date: date
    due_date: date
    total_amount: Decimal
    currency: str = 'USD'
    status: InvoiceStatusType
    notes: str
    metadata: dict = {}
    pdf_bucket: str = ''
    pdf_object_key: str = ''
    pdf_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InvoiceListItemSchema(BaseModel):
    """Enriched invoice schema for admin list view (includes company + subscription names)."""
    id: uuid.UUID
    invoice_number: str
    company_id: uuid.UUID
    company_name: str
    company_nit: str
    subscription_id: uuid.UUID
    subscription_name: str
    company_subscription_id: Optional[uuid.UUID] = None
    issue_date: date
    due_date: date
    total_amount: Decimal
    currency: str = 'USD'
    status: InvoiceStatusType
    notes: str
    metadata: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreateInvoiceSchema(BaseModel):
    invoice_number: str
    company_id: uuid.UUID
    subscription_id: uuid.UUID
    company_subscription_id: Optional[uuid.UUID] = None
    source_charge_id: Optional[uuid.UUID] = None
    issue_date: date
    due_date: date
    total_amount: Decimal
    currency: str = 'USD'
    status: InvoiceStatusType = 'pending'
    notes: str = ''
    metadata: dict = {}


class UpdateInvoiceStatusSchema(BaseModel):
    status: InvoiceStatusType
