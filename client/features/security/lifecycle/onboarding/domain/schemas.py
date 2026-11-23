import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import (
    IdentityFieldError,
    assert_identity_invariants,
    normalize_birth_date,
    normalize_document_number,
    normalize_optional_person_name,
    normalize_phone_country_code,
    normalize_telephone,
)

from .enums import OnboardingStatus, OnboardingStep


# ── Step payloads (input) ────────────────────────────────────────────────────
# Email format is validated upstream by core.validators.Field(is_email=True);
# avoiding EmailStr keeps the optional `pydantic[email]` dep out of the loop.

def _optional_person_name(value: str) -> str:
    try:
        return normalize_optional_person_name(value, field='second_name') or ''
    except IdentityFieldError as exc:
        raise ValueError(str(exc)) from exc


class CompanyStepSchema(BaseModel):
    name: str
    nit: str = ''
    is_registered: bool = True
    address: str
    country: str
    country_code: str
    state: str
    city: str
    city_id: uuid.UUID

    @field_validator('country_code')
    @classmethod
    def _country_code(cls, value: str) -> str:
        cleaned = (value or '').strip().upper()
        if len(cleaned) != 2 or not cleaned.isalpha():
            raise ValueError('country_code must be an ISO 3166-1 alpha-2 code')
        return cleaned

    @model_validator(mode='after')
    def _nit_matches_registration(self):
        if self.is_registered:
            nit = (self.nit or '').strip()
            if len(nit) < 6:
                raise ValueError('nit is required when the company is registered')
            self.nit = nit
        else:
            self.nit = ''
        return self

    def to_storage_dict(self) -> dict:
        return {
            'name': self.name,
            'nit': self.nit,
            'is_registered': self.is_registered,
            'address': self.address,
            'country': self.country,
            'country_code': self.country_code,
            'state': self.state,
            'city': self.city,
            'city_id': str(self.city_id),
        }


class AdminUserStepSchema(BaseModel):
    email: str
    username: str
    telephone: str
    phone_country_code: str
    # Empty string on re-edit means "keep the previously stored hash".
    password: str = ''
    password_confirmation: str = ''
    first_name: str
    second_name: str = ''
    last_name: str
    second_last_name: str
    document_type: IdentityDocumentType
    document_number: str
    birth_date: date

    @field_validator('phone_country_code')
    @classmethod
    def _phone_country_code(cls, value: str) -> str:
        try:
            cleaned = normalize_phone_country_code(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        if not cleaned:
            raise ValueError('phone_country_code must be an ISO 3166-1 alpha-2 code')
        return cleaned

    @field_validator('second_name', mode='before')
    @classmethod
    def _second_name(cls, value) -> str:
        return _optional_person_name('' if value is None else str(value))

    @field_validator('birth_date', mode='before')
    @classmethod
    def _birth_date(cls, value):
        try:
            parsed = normalize_birth_date(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        if parsed is None:
            raise ValueError('birth_date is required')
        return parsed

    @field_validator('document_number')
    @classmethod
    def _document_number(cls, value: str) -> str:
        try:
            cleaned = normalize_document_number(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        return cleaned or ''

    @field_validator('telephone')
    @classmethod
    def _telephone(cls, value: str) -> str:
        try:
            cleaned = normalize_telephone(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        return cleaned or ''

    @model_validator(mode='after')
    def _identity_rules(self):
        try:
            assert_identity_invariants(
                document_type=self.document_type,
                document_number=self.document_number,
                phone_country_code=self.phone_country_code,
                telephone=self.telephone,
            )
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        return self

    def to_public_dict(self) -> dict:
        return {
            'email': str(self.email),
            'username': self.username,
            'telephone': self.telephone,
            'phone_country_code': self.phone_country_code,
            'first_name': self.first_name,
            'second_name': self.second_name,
            'last_name': self.last_name,
            'second_last_name': self.second_last_name,
            'document_type': self.document_type.value,
            'document_number': self.document_number,
            'birth_date': self.birth_date.isoformat(),
        }

    def to_storage_dict(self, hashed_password: str) -> dict:
        payload = self.to_public_dict()
        payload['password_hash'] = hashed_password
        return payload


class SubscriptionStepSchema(BaseModel):
    subscription_id: uuid.UUID
    billing_interval: str = 'monthly'

    @field_validator('billing_interval', mode='before')
    @classmethod
    def _normalize_interval(cls, value):
        from platform.features.billing.subscription.subscription.domain.billing_cycle import (
            normalize_billing_interval,
        )
        return normalize_billing_interval(value)


class OnboardingPlanQuote(BaseModel):
    """Plan activo del catálogo, expuesto al use case de onboarding sin ORM."""
    id: uuid.UUID
    name: str
    price: Decimal
    currency: str = 'USD'


class PaymentStepSchema(BaseModel):
    """Only tokenised payment data ever reaches the backend.

    PAN and CVV are captured and tokenised client-side by the processor SDK.
    """
    processor_token: str
    holder: str
    last4: str
    expiry_month: int
    expiry_year: int


# ── State (output) ───────────────────────────────────────────────────────────

class OnboardingStateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: OnboardingStatus
    current_step: OnboardingStep

    email: str
    nit: str = ''
    schema_name: str = ''

    company_data_completed: bool
    admin_user_completed: bool
    subscription_selected: bool
    payment_completed: bool

    # True iff a password_hash is already stored for the admin user. The
    # frontend uses this to relax the password requirement when the user
    # navigates back to edit the admin step after a resume.
    admin_user_password_set: bool = False

    requires_payment: bool
    subscription_id: Optional[uuid.UUID] = None

    company_data: dict = {}
    subscription_data: dict = {}
    # Non-sensitive subset of admin_user_data — never includes password_hash.
    admin_user_data: dict = {}
    # Non-sensitive subset of payment_data — never includes processor_token.
    payment_data: dict = {}

    expires_at: str


class FinalizeResultSchema(BaseModel):
    registration_id: uuid.UUID
    company_id: uuid.UUID
    email_confirmation_required: bool
