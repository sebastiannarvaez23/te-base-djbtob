from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_LOCALES = frozenset({'es', 'en'})
_MAX_MESSAGE = 2000
_MAX_LABEL = 200


def _strip(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip()


def _require_text(value: str, *, field: str) -> str:
    cleaned = (value or '').strip()
    if not cleaned:
        raise ValueError(f'{field} must not be blank')
    return cleaned


class AuthorSnapshot(BaseModel):
    id: uuid.UUID
    display_name: str
    company_name: str
    is_active: bool
    role: str = ''


class TestimonialSchema(BaseModel):
    __test__ = False

    id: uuid.UUID
    author_id: uuid.UUID
    score: int = Field(ge=1, le=5)
    message: str
    author_name: str
    author_role: str = ''
    company_name: str = ''
    locale: str = 'es'
    is_published: bool = False
    sort_order: int = 0
    content_hash: str = ''
    seal: str = ''
    seal_algorithm: str = ''
    canonical_payload: str = ''
    signed_at: Optional[datetime] = None
    signatory_id: str = ''
    tenant_id: str = ''
    ip_address: str = ''
    user_agent: str = ''
    request_id: str = ''
    channel: str = ''
    revoked_at: Optional[datetime] = None
    superseded_by: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class PublicTestimonialSchema(BaseModel):
    """Narrow public projection for base-landing-web."""

    id: uuid.UUID
    score: int = Field(ge=1, le=5)
    message: str
    author_name: str
    author_role: str = ''
    company_name: str = ''
    locale: str = 'es'
    signed_at: datetime
    seal_fingerprint: str


class CreateTestimonialSchema(BaseModel):
    """Admin catalog create — unsigned quote, no seal fields."""

    author_id: uuid.UUID
    score: int = Field(ge=1, le=5)
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)
    author_name: Optional[str] = Field(default=None, max_length=_MAX_LABEL)
    author_role: str = Field(default='', max_length=_MAX_LABEL)
    company_name: Optional[str] = Field(default=None, max_length=_MAX_LABEL)
    locale: str = 'es'
    is_published: bool = False
    sort_order: int = Field(default=0, ge=0, le=32767)

    @field_validator('message')
    @classmethod
    def _message(cls, value: str) -> str:
        return _require_text(value, field='message')

    @field_validator('author_name', 'company_name')
    @classmethod
    def _optional_label(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _strip(value)
        return cleaned or None

    @field_validator('author_role')
    @classmethod
    def _role(cls, value: str) -> str:
        return (_strip(value) or '')

    @field_validator('locale')
    @classmethod
    def _locale(cls, value: str) -> str:
        locale = (value or '').strip().lower()
        if locale not in _LOCALES:
            raise ValueError('locale must be es or en')
        return locale


class SignedTestimonialDraft(BaseModel):
    """Client submit: a new signed document ready to persist."""

    id: uuid.UUID
    author_id: uuid.UUID
    score: int = Field(ge=1, le=5)
    message: str = Field(min_length=10, max_length=_MAX_MESSAGE)
    author_name: str = Field(min_length=1, max_length=_MAX_LABEL)
    author_role: str = Field(default='', max_length=_MAX_LABEL)
    company_name: str = Field(default='', max_length=_MAX_LABEL)
    locale: str = 'es'
    is_published: bool = True
    sort_order: int = Field(default=0, ge=0, le=32767)
    content_hash: str = Field(min_length=64, max_length=64)
    seal: str = Field(min_length=64, max_length=64)
    seal_algorithm: str = Field(min_length=1, max_length=32)
    canonical_payload: str = Field(min_length=1)
    signed_at: datetime
    signatory_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(default='', max_length=64)
    ip_address: str = Field(default='', max_length=64)
    user_agent: str = Field(default='', max_length=512)
    request_id: str = Field(default='', max_length=64)
    channel: str = Field(default='web', max_length=32)

    @field_validator('locale')
    @classmethod
    def _locale(cls, value: str) -> str:
        locale = (value or '').strip().lower()
        if locale not in _LOCALES:
            raise ValueError('locale must be es or en')
        return locale


class TestimonialListFilters(BaseModel):
    """Typed list filters — no loose dicts into the repository."""

    __test__ = False

    q: Optional[str] = Field(default=None, max_length=200)
    author_id: Optional[uuid.UUID] = None
    score: Optional[int] = Field(default=None, ge=1, le=5)
    is_published: Optional[bool] = None
    locale: Optional[str] = None
    signed: Optional[bool] = None

    @classmethod
    def from_query(cls, filters: dict) -> TestimonialListFilters:
        allowed = cls.model_fields
        return cls(**{key: value for key, value in (filters or {}).items() if key in allowed})

    @field_validator('locale')
    @classmethod
    def _locale(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        locale = value.strip().lower()
        if locale not in _LOCALES:
            raise ValueError('locale must be es or en')
        return locale


class TestimonialPage(BaseModel):
    __test__ = False

    items: list[TestimonialSchema]
    total: int = Field(ge=0)


class PublicTestimonialPage(BaseModel):
    items: list[PublicTestimonialSchema]
    total: int = Field(ge=0)


class UpdateTestimonialSchema(BaseModel):
    author_id: Optional[uuid.UUID] = None
    score: Optional[int] = Field(default=None, ge=1, le=5)
    message: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_MESSAGE)
    author_name: Optional[str] = Field(default=None, max_length=_MAX_LABEL)
    author_role: Optional[str] = Field(default=None, max_length=_MAX_LABEL)
    company_name: Optional[str] = Field(default=None, max_length=_MAX_LABEL)
    locale: Optional[str] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=32767)
    content_hash: Optional[str] = None
    seal: Optional[str] = None
    seal_algorithm: Optional[str] = None
    canonical_payload: Optional[str] = None
    signed_at: Optional[datetime] = None
    signatory_id: Optional[str] = None
    tenant_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    channel: Optional[str] = None

    @field_validator('message')
    @classmethod
    def _message(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_text(value, field='message')

    @field_validator('author_name', 'company_name', 'author_role')
    @classmethod
    def _label(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _strip(value) or ''

    @field_validator('locale')
    @classmethod
    def _locale(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        locale = value.strip().lower()
        if locale not in _LOCALES:
            raise ValueError('locale must be es or en')
        return locale


class SubmitMyTestimonialSchema(BaseModel):
    """Company user submitting their own quote (author comes from the session)."""

    author_id: uuid.UUID
    score: int = Field(ge=1, le=5)
    message: str = Field(min_length=10, max_length=_MAX_MESSAGE)
    locale: str = 'es'
    accepted: bool
    tenant_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    channel: str = 'web'

    @field_validator('message')
    @classmethod
    def _message(cls, value: str) -> str:
        return _require_text(value, field='message')

    @field_validator('locale')
    @classmethod
    def _locale(cls, value: str) -> str:
        locale = (value or '').strip().lower()
        if locale not in _LOCALES:
            raise ValueError('locale must be es or en')
        return locale

    @field_validator('accepted')
    @classmethod
    def _accepted(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError('accepted must be true')
        return value


def resolve_attribution(
    snapshot: AuthorSnapshot,
    *,
    author_name: Optional[str] = None,
    company_name: Optional[str] = None,
    existing: Optional[TestimonialSchema] = None,
) -> tuple[str, str]:
    """Prefer explicit overrides, then the current row, then the user snapshot."""
    name = (author_name or '').strip()
    if not name:
        name = existing.author_name if existing else snapshot.display_name
    company = (company_name or '').strip()
    if not company:
        company = existing.company_name if existing else snapshot.company_name
    return name, company


def project_public(row: TestimonialSchema) -> PublicTestimonialSchema:
    """Public DTO for a row that already carries a seal (caller verified)."""
    if not row.signed_at or not row.seal:
        raise ValueError('unsigned testimonial cannot be projected publicly')
    return PublicTestimonialSchema(
        id=row.id,
        score=row.score,
        message=row.message,
        author_name=row.author_name,
        author_role=row.author_role,
        company_name=row.company_name,
        locale=row.locale,
        signed_at=row.signed_at,
        seal_fingerprint=row.seal[:8],
    )


class TestimonialPromptSettingsSchema(BaseModel):
    __test__ = False

    prompt_enabled: bool = True
    frequency_days: int = Field(default=30, ge=0, le=365)
    first_appearance_days: int = Field(default=0, ge=0, le=365)
    login_delay_seconds: int = Field(default=0, ge=0, le=300)
    ask_after_submit: bool = False


class UpdateTestimonialPromptSettingsSchema(BaseModel):
    prompt_enabled: Optional[bool] = None
    frequency_days: Optional[int] = Field(default=None, ge=0, le=365)
    first_appearance_days: Optional[int] = Field(default=None, ge=0, le=365)
    login_delay_seconds: Optional[int] = Field(default=None, ge=0, le=300)
    ask_after_submit: Optional[bool] = None


class TestimonialPromptDecisionSchema(BaseModel):
    __test__ = False

    should_prompt: bool
    delay_seconds: int = Field(default=0, ge=0, le=300)


class TestimonialPromptReceiptSchema(BaseModel):
    __test__ = False

    user_id: uuid.UUID
    last_prompted_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    pending_reprompt: bool = False


class RepromptTestimonialsSchema(BaseModel):
    author_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class RepromptTestimonialsResultSchema(BaseModel):
    requested: int = Field(ge=0)
