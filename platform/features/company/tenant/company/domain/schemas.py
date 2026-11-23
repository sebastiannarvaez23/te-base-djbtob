import uuid
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class DomainSchema(BaseModel):
    id: uuid.UUID
    domain: str
    is_primary: bool

    model_config = {"from_attributes": True}


class CompanySchema(BaseModel):
    id: Optional[uuid.UUID] = None
    schema_name: str
    nit: str
    name: str
    address: str
    geo_city_id: uuid.UUID
    country: str = ''
    state: str = ''
    city: str = ''
    lifecycle: str = 'ACTIVE'
    closed_at: Optional[str] = None
    purge_after: Optional[str] = None
    closed_reason: str = ''
    legal_hold: bool = False
    legal_hold_reason: str = ''
    export_attested_at: Optional[str] = None
    export_object_key: str = ''

    model_config = {"from_attributes": True}


class CompanySubscriptionSchema(BaseModel):
    id: uuid.UUID
    subscription_name: str
    subscription_code: str
    status: str
    start_date: str
    end_date: str
    billing_interval: str = 'monthly'


class CompanyDetailSubscriptionSchema(BaseModel):
    """Subscription summary shaped for the client settings screen."""
    id: uuid.UUID
    name: str
    status: str
    end_date: str
    billing_interval: str = 'monthly'


class CompanyDetailSchema(BaseModel):
    """Single-company detail with the extra fields the settings screen shows
    (primary domain, creation date and the latest subscription)."""
    id: uuid.UUID
    schema_name: str
    nit: str
    name: str
    address: str
    geo_city_id: uuid.UUID
    country: str = ''
    state: str = ''
    city: str = ''
    country_code: str = ''
    state_code: str = ''
    city_code: str = ''
    domain: Optional[str] = None
    created_at: Optional[str] = None
    subscription: Optional[CompanyDetailSubscriptionSchema] = None
    is_registered: bool = True
    lifecycle: str = 'ACTIVE'
    closed_at: Optional[str] = None
    purge_after: Optional[str] = None
    closed_reason: str = ''
    legal_hold: bool = False
    legal_hold_reason: str = ''
    export_attested_at: Optional[str] = None
    export_object_key: str = ''


class CompanyListItemSchema(BaseModel):
    id: uuid.UUID
    schema_name: str
    nit: str
    name: str
    address: str
    geo_city_id: uuid.UUID
    country: str = ''
    state: str = ''
    city: str = ''
    is_active: bool
    created: str
    subscription: Optional[CompanySubscriptionSchema] = None
    lifecycle: str = 'ACTIVE'
    closed_at: Optional[str] = None
    purge_after: Optional[str] = None
    closed_reason: str = ''
    legal_hold: bool = False
    legal_hold_reason: str = ''
    export_attested_at: Optional[str] = None
    export_object_key: str = ''


class CreateCompanySchema(BaseModel):
    schema_name: str
    nit: str
    name: str
    address: str
    geo_city_id: uuid.UUID
    subscription_id: uuid.UUID
    billing_interval: str = 'monthly'

    @field_validator('billing_interval', mode='before')
    @classmethod
    def _normalize_interval(cls, value):
        from platform.features.billing.subscription.subscription.domain.billing_cycle import (
            normalize_billing_interval,
        )
        return normalize_billing_interval(value)


class UpdateCompanySchema(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    nit: Optional[str] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError('name must be at least 2 characters')
        return cleaned

    @field_validator('address')
    @classmethod
    def _address(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise ValueError('address must be at least 5 characters')
        return cleaned

    @field_validator('nit')
    @classmethod
    def _nit(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().replace('.', '')
        if cleaned and len(cleaned) < 6:
            raise ValueError('nit must have at least 6 characters')
        return cleaned


class CloseCompanySchema(BaseModel):
    company_id: uuid.UUID
    reason: str
    actor_admin_id: Optional[uuid.UUID] = None
    grace_days: int = 30
    spare_user_id: Optional[uuid.UUID] = None


class SelfCloseCompanySchema(BaseModel):
    company_id: uuid.UUID
    confirmation: str
    actor_user_id: uuid.UUID
    grace_days: int = 30
    accepted: bool = False
    country: Optional[str] = None


class CompleteSelfCloseSchema(BaseModel):
    company_id: uuid.UUID
    actor_user_id: uuid.UUID
    reason: str = ''


class ReopenCompanySchema(BaseModel):
    company_id: uuid.UUID
    actor_admin_id: Optional[uuid.UUID] = None


class CompanyLifecycleRecord(BaseModel):
    id: uuid.UUID
    schema_name: str
    nit: str
    name: str
    lifecycle: str
    closed_at: Optional[str] = None
    purge_after: Optional[str] = None
    closed_reason: str = ''
    legal_hold: bool = False
    legal_hold_reason: str = ''
    export_attested_at: Optional[str] = None
    export_object_key: str = ''
    export_attested_by: Optional[uuid.UUID] = None
    user_ids: list[uuid.UUID] = Field(default_factory=list)
    users_tombstoned: int = 0
    schema_dropped: bool = False


class SetLegalHoldSchema(BaseModel):
    company_id: uuid.UUID
    enabled: bool
    reason: str = ''
    actor_admin_id: Optional[uuid.UUID] = None


class ExportClosedTenantSchema(BaseModel):
    company_id: uuid.UUID
    waived: bool = False
    reason: str = ''
    actor_admin_id: Optional[uuid.UUID] = None


class PurgeClosedCompanySchema(BaseModel):
    company_id: uuid.UUID
    force: bool = False
    reason: str = ''
    actor_admin_id: Optional[uuid.UUID] = None
    dry_run: bool = False


class TenantExportDownloadSchema(BaseModel):
    company_id: uuid.UUID
    object_key: str
    download_url: str
    attested_at: Optional[str] = None
