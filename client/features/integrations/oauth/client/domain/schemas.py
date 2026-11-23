"""Pydantic schemas for Integration Application OAuth.

Domain contracts are strict: lengths, literals, unknown keys forbidden and
English validation messages. Presentation maps ``RequestBody`` output
through ``parse_*`` helpers (same pattern as warehouse orders).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError, field_validator

from core.errors import AppErrorCode, ValidationAppException

EnvironmentLiteral = Literal['CLIENT_TEST', 'CLIENT_PROD']
StatusLiteral = Literal['ACTIVE', 'DISABLED', 'REVOKED']
GrantTypeLiteral = Literal['client_credentials']

MAX_SCOPES = 32
MAX_SCOPE_LENGTH = 100
SCOPE_KEY_PATTERN = r'[a-z0-9][a-z0-9._:-]*'
SCOPE_KEY_RE = re.compile(SCOPE_KEY_PATTERN)

_STRICT_INPUT = ConfigDict(extra='forbid')


def _first_pydantic_message(exc: PydanticValidationError) -> str:
    first = exc.errors()[0]
    loc = '.'.join(str(part) for part in first.get('loc', ()) if part != 'body')
    msg = first.get('msg') or 'Invalid value'
    return f'{loc}: {msg}' if loc else msg


def _parse_or_raise(model_cls, **kwargs):
    try:
        return model_cls(**kwargs)
    except PydanticValidationError as exc:
        raise ValidationAppException(
            AppErrorCode.VALIDATION_ERROR,
            override_detail=_first_pydantic_message(exc),
        ) from exc


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < 2:
        raise ValueError('name must have at least 2 characters after trimming.')
    return cleaned


def _clean_scopes(value: List[str]) -> List[str]:
    cleaned: list[str] = []
    for item in value:
        scope = item.strip()
        if not scope:
            raise ValueError('scopes cannot contain empty strings.')
        if len(scope) > MAX_SCOPE_LENGTH:
            raise ValueError(f'each scope must be at most {MAX_SCOPE_LENGTH} characters.')
        if not SCOPE_KEY_RE.fullmatch(scope):
            raise ValueError('scopes must be lowercase functionality keys.')
        cleaned.append(scope)
    return cleaned


class IntegrationScopeSchema(BaseModel):
    """An API-category functionality that can be granted as an OAuth scope."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, max_length=MAX_SCOPE_LENGTH)
    label: str
    module: str
    module_name: str


class IntegrationApplicationSchema(BaseModel):
    id: uuid.UUID
    name: str
    description: str = ''
    client_id: str
    status: StatusLiteral
    environment: EnvironmentLiteral
    scopes: List[str] = Field(default_factory=list)
    secret_prefix: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateIntegrationApplicationSchema(BaseModel):
    model_config = _STRICT_INPUT

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default='', max_length=2000)
    environment: EnvironmentLiteral = 'CLIENT_TEST'
    scopes: List[str] = Field(min_length=1, max_length=MAX_SCOPES)

    @field_validator('name')
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator('description')
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator('scopes')
    @classmethod
    def normalize_scopes(cls, value: List[str]) -> List[str]:
        return _clean_scopes(value)


class UpdateIntegrationApplicationSchema(BaseModel):
    """Editable metadata only — status changes go through lifecycle use cases."""

    model_config = _STRICT_INPUT

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    environment: Optional[EnvironmentLiteral] = None
    scopes: Optional[List[str]] = Field(default=None, min_length=1, max_length=MAX_SCOPES)

    @field_validator('name')
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_name(value)

    @field_validator('description')
    @classmethod
    def strip_description(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else value.strip()

    @field_validator('scopes')
    @classmethod
    def normalize_scopes(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return None if value is None else _clean_scopes(value)

    def has_changes(self) -> bool:
        return bool(self.model_dump(exclude_none=True))


class GeneratedSecretSchema(BaseModel):
    """Freshly minted client secret: raw value (shown once) + storable digest."""

    model_config = ConfigDict(frozen=True)

    raw: str = Field(min_length=32, max_length=128, repr=False)
    digest: str = Field(min_length=1, max_length=128, repr=False)
    prefix: str = Field(min_length=1, max_length=12)


class CreatedApplicationCredentialsSchema(BaseModel):
    """Returned once on create/rotate — includes raw client_secret."""

    application: IntegrationApplicationSchema
    client_secret: str = Field(min_length=16, max_length=128, repr=False)


class IssueTokenInputSchema(BaseModel):
    model_config = _STRICT_INPUT

    grant_type: GrantTypeLiteral
    client_id: str = Field(min_length=8, max_length=64)
    client_secret: str = Field(min_length=16, max_length=128, repr=False)
    scope: Optional[str] = Field(default=None, max_length=500)

    @field_validator('grant_type', mode='before')
    @classmethod
    def normalize_grant_type(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator('client_id', 'client_secret')
    @classmethod
    def strip_credentials(cls, value: str) -> str:
        return value.strip()

    @field_validator('scope')
    @classmethod
    def strip_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IssuedTokenSchema(BaseModel):
    access_token: str
    token_type: str = 'Bearer'
    expires_in: int = Field(gt=0)
    scope: str = ''


def parse_create_integration_application_schema(**kwargs) -> CreateIntegrationApplicationSchema:
    return _parse_or_raise(CreateIntegrationApplicationSchema, **kwargs)


def parse_update_integration_application_schema(**kwargs) -> UpdateIntegrationApplicationSchema:
    return _parse_or_raise(UpdateIntegrationApplicationSchema, **kwargs)


def parse_issue_token_input_schema(**kwargs) -> IssueTokenInputSchema:
    return _parse_or_raise(IssueTokenInputSchema, **kwargs)
