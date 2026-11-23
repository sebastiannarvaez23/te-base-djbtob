from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ValidationInfo, field_validator, model_validator

from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType
from client.features.security.lifecycle.registration.domain.identity import (
    IdentityFieldError,
    assert_identity_invariants,
    normalize_birth_date,
    normalize_document_number,
    normalize_document_type,
    normalize_optional_person_name,
)
from client.features.security.lifecycle.registration.domain.schemas import RolSchema  # noqa: F401


class CompanyUserSchema(BaseModel):
    id: UUID
    first_name: Optional[str] = None
    second_name: str = ''
    last_name: Optional[str] = None
    second_last_name: str = ''
    document_type: str = ''
    document_number: str = ''
    birth_date: Optional[date] = None
    email: str
    username: str
    telephone: str
    rol: RolSchema
    is_active: bool
    # Public URL of the profile picture, or None when the user has no custom
    # picture (the UI then falls back to the initials avatar).
    picture: Optional[str] = None


def _optional_name(value, field: str) -> str:
    try:
        return normalize_optional_person_name('' if value is None else value, field=field) or ''
    except IdentityFieldError as exc:
        raise ValueError(str(exc)) from exc


class CreateCompanyUserSchema(BaseModel):
    first_name: str
    second_name: str = ''
    last_name: str
    second_last_name: str
    document_type: IdentityDocumentType
    document_number: str
    birth_date: date
    email: str
    username: str
    telephone: str
    password: Optional[str] = None
    rol_id: UUID
    company_id: UUID

    @field_validator('second_name', mode='before')
    @classmethod
    def _second_name(cls, value) -> str:
        return _optional_name(value, 'second_name')

    @field_validator('second_last_name', mode='before')
    @classmethod
    def _second_last_name(cls, value) -> str:
        cleaned = _optional_name(value, 'second_last_name')
        if not cleaned:
            raise ValueError('second_last_name is required')
        return cleaned

    @field_validator('document_type', mode='before')
    @classmethod
    def _document_type(cls, value):
        try:
            cleaned = normalize_document_type(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        if not cleaned:
            raise ValueError('document_type is required')
        return cleaned

    @field_validator('document_number')
    @classmethod
    def _document_number(cls, value: str) -> str:
        try:
            cleaned = normalize_document_number(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        if not cleaned:
            raise ValueError('document_number is required')
        return cleaned

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

    @model_validator(mode='after')
    def _identity_rules(self):
        try:
            assert_identity_invariants(
                document_type=self.document_type,
                document_number=self.document_number,
            )
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        return self


class UpdateCompanyUserSchema(BaseModel):
    first_name: Optional[str] = None
    second_name: Optional[str] = None
    last_name: Optional[str] = None
    second_last_name: Optional[str] = None
    document_type: Optional[IdentityDocumentType] = None
    document_number: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    password: Optional[str] = None
    rol_id: Optional[UUID] = None

    @field_validator('second_name', 'second_last_name', mode='before')
    @classmethod
    def _optional_names(cls, value, info: ValidationInfo):
        if value is None:
            return None
        return _optional_name(value, info.field_name)

    @field_validator('document_type', mode='before')
    @classmethod
    def _document_type(cls, value):
        if value is None or value == '':
            return None
        try:
            return normalize_document_type(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('document_number')
    @classmethod
    def _document_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            return normalize_document_number(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator('birth_date', mode='before')
    @classmethod
    def _birth_date(cls, value):
        if value is None or value == '':
            return None
        try:
            return normalize_birth_date(value)
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode='after')
    def _identity_rules(self):
        try:
            assert_identity_invariants(
                document_type=self.document_type,
                document_number=self.document_number,
            )
        except IdentityFieldError as exc:
            raise ValueError(str(exc)) from exc
        return self
