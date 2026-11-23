import uuid
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentMethodSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    company_id: uuid.UUID
    name: str
    provider: str
    holder: str = ''
    last4: str = ''
    expiry: str = ''
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreatePaymentMethodSchema(BaseModel):
    company_id: uuid.UUID
    name: str
    provider: str
    holder: str = ''
    last4: str = ''
    expiry: str = ''
    is_active: bool = True


class UpdatePaymentMethodSchema(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    holder: Optional[str] = None
    last4: Optional[str] = None
    expiry: Optional[str] = None
    is_active: Optional[bool] = None
