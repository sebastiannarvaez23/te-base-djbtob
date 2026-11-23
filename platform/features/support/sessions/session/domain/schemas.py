"""Pydantic contracts for live support sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from platform.features.support.sessions.session.domain.constants import (
    DEFAULT_QUEUE_WAIT_MINUTES,
    SENDER_AGENT,
    SENDER_CLIENT,
    SENDER_SYSTEM,
    STATUS_ACTIVE,
    STATUS_AWAITING_RATING,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_QUEUED,
)

SupportSessionStatus = Literal[
    'QUEUED',
    'ACTIVE',
    'AWAITING_RATING',
    'CLOSED',
    'CANCELLED',
]
SupportSenderKind = Literal['CLIENT', 'AGENT', 'SYSTEM']

_VALID_STATUSES = frozenset({
    STATUS_QUEUED,
    STATUS_ACTIVE,
    STATUS_AWAITING_RATING,
    STATUS_CLOSED,
    STATUS_CANCELLED,
})
_VALID_SENDERS = frozenset({SENDER_CLIENT, SENDER_AGENT, SENDER_SYSTEM})


def normalize_whatsapp_url(value: str | None) -> str:
    """Empty string or absolute http(s) URL; raises ValueError otherwise."""
    cleaned = (value or '').strip()
    if not cleaned:
        return ''
    parsed = urlparse(cleaned)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('whatsapp_url must be an absolute http(s) URL')
    return cleaned


class CreateSupportSessionSchema(BaseModel):
    motive: str = Field(min_length=1, max_length=4000)
    company_id: str = Field(min_length=1, max_length=64)
    schema_name: str = Field(min_length=1, max_length=63)
    company_name: str = Field(default='', max_length=200)
    requester_user_id: UUID
    requester_username: str = Field(default='', max_length=150)
    requester_display_name: str = Field(default='', max_length=200)


class SendSupportMessageSchema(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class RateSupportSessionSchema(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default='', max_length=500)


class AcceptSupportSessionSchema(BaseModel):
    admin_user_id: UUID
    admin_label: str = Field(default='', max_length=200)


class SupportSessionMessageView(BaseModel):
    id: UUID
    session_id: UUID
    sender_kind: SupportSenderKind
    sender_user_id: Optional[UUID] = None
    body: str
    created_at: datetime

    @field_validator('sender_kind', mode='before')
    @classmethod
    def _sender_kind(cls, value: str) -> str:
        if value not in _VALID_SENDERS:
            raise ValueError(f'invalid sender_kind: {value}')
        return value


class SupportSessionEventView(BaseModel):
    id: UUID
    session_id: UUID
    event_type: str
    actor_kind: str = ''
    actor_user_id: Optional[UUID] = None
    actor_label: str = ''
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SupportSessionView(BaseModel):
    id: UUID
    company_id: str
    schema_name: str
    company_name: str
    requester_user_id: UUID
    requester_username: str
    requester_display_name: str
    motive: str
    status: SupportSessionStatus
    accepted_by_id: Optional[UUID] = None
    accepted_by_label: str = ''
    client_unread_count: int = 0
    agent_unread_count: int = 0
    rating: Optional[int] = None
    rating_comment: str = ''
    queued_at: datetime
    accepted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    rated_at: Optional[datetime] = None
    updated_at: datetime

    @field_validator('status', mode='before')
    @classmethod
    def _status(cls, value: str) -> str:
        if value not in _VALID_STATUSES:
            raise ValueError(f'invalid status: {value}')
        return value


class SupportSessionListFilters(BaseModel):
    status: Optional[SupportSessionStatus] = None
    company: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    search: Optional[str] = None

    @field_validator('status', mode='before')
    @classmethod
    def _filter_status(cls, value: str | None) -> str | None:
        if value is None or value == '':
            return None
        if value not in _VALID_STATUSES:
            raise ValueError(f'invalid status: {value}')
        return value


class SupportSettingsSchema(BaseModel):
    queue_wait_timeout_minutes: int = Field(
        default=DEFAULT_QUEUE_WAIT_MINUTES, ge=1, le=180,
    )
    whatsapp_url: str = Field(default='', max_length=500)
    phone_line: str = Field(default='', max_length=64)

    @field_validator('whatsapp_url', mode='before')
    @classmethod
    def _whatsapp_url(cls, value: str | None) -> str:
        return normalize_whatsapp_url(value)


class UpdateSupportSettingsSchema(BaseModel):
    queue_wait_timeout_minutes: Optional[int] = Field(default=None, ge=1, le=180)
    whatsapp_url: Optional[str] = Field(default=None, max_length=500)
    phone_line: Optional[str] = Field(default=None, max_length=64)

    @field_validator('whatsapp_url', mode='before')
    @classmethod
    def _whatsapp_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_whatsapp_url(value)
