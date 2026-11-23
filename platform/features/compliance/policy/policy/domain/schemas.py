"""Contratos Pydantic del dominio de políticas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .enums import PolicyAudience, PolicyCountryStatus, PolicySubjectType

_COUNTRY_RE = re.compile(r'^[A-Z]{2}$')
_CODE_RE = re.compile(r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$')


def normalize_country(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _COUNTRY_RE.match(cleaned):
        raise ValueError('country must be an ISO 3166-1 alpha-2 code (e.g. CO or US)')
    return cleaned


def normalize_code(value: str) -> str:
    cleaned = (value or '').strip().upper()
    if not _CODE_RE.match(cleaned):
        raise ValueError('code must be an uppercase kebab-case slug (e.g. DATA-PROCESSING)')
    return cleaned


class PolicyCountrySummarySchema(BaseModel):
    """Metadatos de una versión por país (sin el markdown)."""

    id: uuid.UUID
    country: str
    version: int = 0
    status: PolicyCountryStatus = PolicyCountryStatus.DRAFT
    title: str
    object_key: str
    content_hash: str
    byte_size: int
    change_summary: str = ''
    revoked_at: Optional[datetime] = None
    revoked_reason: str = ''
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    has_draft: bool = False

    model_config = {'from_attributes': True}


class PolicySchema(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    audience: PolicyAudience
    description: str = ''
    is_active: bool = True
    countries: List[PolicyCountrySummarySchema] = Field(default_factory=list)
    drafts: List[PolicyCountrySummarySchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreatePolicySchema(BaseModel):
    code: str
    name: str
    audience: PolicyAudience
    description: str = ''
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_code(value)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('name must not be blank')
        return cleaned


class UpdatePolicySchema(BaseModel):
    """Código y audiencia son inmutables tras el alta (rutas MinIO)."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('name must not be blank')
        return cleaned


class UpsertPolicyCountrySchema(BaseModel):
    """Payload de borrador (guardar). País viene de la ruta al liberar/start."""

    title: str
    markdown: str

    @field_validator('title')
    @classmethod
    def _title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('title must not be blank')
        return cleaned

    @field_validator('markdown')
    @classmethod
    def _markdown(cls, value: str) -> str:
        # Drafts may be saved empty while editing; release validates non-empty.
        return value or ''


class SavePolicyCountryDraftSchema(BaseModel):
    title: str
    markdown: str

    @field_validator('title')
    @classmethod
    def _title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('title must not be blank')
        return cleaned

    @field_validator('markdown')
    @classmethod
    def _markdown(cls, value: str) -> str:
        return value or ''


class PolicyCountryContentSchema(BaseModel):
    """Contenido completo de una versión (publicado o borrador)."""

    policy_id: uuid.UUID
    policy_code: str
    audience: PolicyAudience
    country: str
    version: int
    status: PolicyCountryStatus
    title: str
    markdown: str
    object_key: str
    content_hash: str
    byte_size: int
    change_summary: str = ''
    updated_at: Optional[datetime] = None


class PublishPolicyCountryResultSchema(BaseModel):
    """Resultado de aprobar+liberar un borrador."""

    country: PolicyCountrySummarySchema
    created_new_version: bool
    revoked_version: Optional[int] = None


class ReleasePolicyCountryDraftSchema(BaseModel):
    """Payload de liberación. El resumen es obligatorio si ya hay versión publicada."""

    change_summary: str = ''

    @field_validator('change_summary')
    @classmethod
    def _summary(cls, value: str) -> str:
        return (value or '').strip()


class SignatoryRef(BaseModel):
    """Identidad del firmante (admin o usuario de tenant)."""

    subject_type: PolicySubjectType
    subject_id: str
    tenant_id: Optional[str] = None

    @field_validator('subject_id')
    @classmethod
    def _subject(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('subject_id must not be blank')
        return cleaned

    @field_validator('tenant_id')
    @classmethod
    def _tenant(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SignPolicyContextSchema(BaseModel):
    """Contexto de request capturado al firmar."""

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    channel: str = 'web'
    signed_at: Optional[datetime] = None


class SignPolicySchema(BaseModel):
    policy_id: uuid.UUID
    country: str
    signatory: SignatoryRef
    context: SignPolicyContextSchema = Field(default_factory=SignPolicyContextSchema)

    @field_validator('country')
    @classmethod
    def _country(cls, value: str) -> str:
        return normalize_country(value)


class PolicySignatureSchema(BaseModel):
    id: uuid.UUID
    policy_id: uuid.UUID
    policy_code: str
    policy_country_id: uuid.UUID
    country: str
    content_hash: str
    subject_type: PolicySubjectType
    subject_id: str
    tenant_id: Optional[str] = None
    signed_at: datetime
    seal: str
    seal_algorithm: str
    canonical_payload: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    channel: str = 'web'

    model_config = {'from_attributes': True}


class PendingPolicySchema(BaseModel):
    """Política activa pendiente de firma para el sujeto (versión publicada por país)."""

    policy_id: uuid.UUID
    code: str
    name: str
    audience: PolicyAudience
    country: str
    version: int
    title: str
    content_hash: str
    policy_country_id: uuid.UUID


class PolicySignatureVerificationSchema(BaseModel):
    signature_id: uuid.UUID
    valid: bool
    reason: Optional[str] = None
