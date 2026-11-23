import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core.validators import (
    OptionalDateFormatValue,
    OptionalTimeFormatValue,
    DateFormatValue,
    TimeFormatValue,
)

from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import (
    IdentityFieldError,
    assert_identity_invariants,
    normalize_document_number,
    normalize_document_type,
    normalize_optional_person_name,
    normalize_phone_country_code,
    normalize_telephone,
)


class UserPreferencesSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    language: str
    theme: str
    timezone: str
    date_format: DateFormatValue
    time_format: TimeFormatValue
    sidebar_collapsed: bool
    items_per_page: int
    notifications_enabled: bool
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UpdateUserPreferencesSchema(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None
    date_format: OptionalDateFormatValue = None
    time_format: OptionalTimeFormatValue = None
    sidebar_collapsed: Optional[bool] = None
    items_per_page: Optional[int] = Field(default=None, ge=5, le=200)
    notifications_enabled: Optional[bool] = None


class UserProfileSchema(BaseModel):
    id: uuid.UUID
    username: str
    first_name: Optional[str] = None
    second_name: str = ''
    last_name: Optional[str] = None
    second_last_name: str = ''
    document_type: str = ''
    document_number: str = ''
    email: str
    telephone: str
    phone_country_code: str = 'CO'
    # Relative media path (e.g. /media/perfil/x.jpg); the API layer turns it
    # into an absolute URL using the request.
    picture: Optional[str] = None
    rol_name: Optional[str] = None
    company_name: Optional[str] = None

    model_config = {"from_attributes": True}


class UpdateUserProfileSchema(BaseModel):
    first_name: Optional[str] = None
    second_name: Optional[str] = None
    last_name: Optional[str] = None
    second_last_name: Optional[str] = None
    document_type: Optional[IdentityDocumentType] = None
    document_number: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    phone_country_code: Optional[str] = None

    @field_validator('phone_country_code')
    @classmethod
    def _phone_country_code(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_phone_country_code(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('second_name', 'second_last_name', mode='before')
    @classmethod
    def _optional_name(cls, value):
        try:
            return normalize_optional_person_name(value, field='optional_name')
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('document_type', mode='before')
    @classmethod
    def _document_type(cls, value):
        try:
            return normalize_document_type(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('document_number')
    @classmethod
    def _document_number(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_document_number(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('telephone')
    @classmethod
    def _telephone(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_telephone(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

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
