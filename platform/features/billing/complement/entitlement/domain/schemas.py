import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ComplementCatalogItemSchema(BaseModel):
    id: uuid.UUID
    kind: str = 'functionality'
    key: str
    label: str
    module: str
    billing_mode: str
    category: str


class CompanyComplementSchema(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    functionality_id: Optional[uuid.UUID] = None
    module_id: Optional[uuid.UUID] = None
    functionality_key: str
    functionality_label: str
    module_code: str
    billing_mode: str
    status: str
    source: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    notes: str = ''
    auto_renew: bool = False
    catalog_service_id: Optional[uuid.UUID] = None
    price_paid: Optional[Decimal] = None
    currency: str = ''
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class GrantComplementSchema(BaseModel):
    company_id: uuid.UUID
    functionality_id: Optional[uuid.UUID] = None
    module_id: Optional[uuid.UUID] = None
    notes: str = ''
    granted_by_id: Optional[uuid.UUID] = None


class RevokeComplementSchema(BaseModel):
    company_id: uuid.UUID
    entitlement_id: uuid.UUID
    notes: str = ''


class ComplementFunctionalitySchema(BaseModel):
    id: uuid.UUID
    key: str
    billing_mode: str
