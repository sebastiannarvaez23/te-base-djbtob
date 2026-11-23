from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from core.flags.domain.enums import FlagStatus, FlagType, ScopeType

_KEY_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$')


class FeatureFlagScopeSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    scope_type: str
    scope_value: str
    is_active: bool = True

    model_config = {'from_attributes': True}


class FeatureFlagSchema(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str = ''
    flag_type: str
    status: str
    enabled: bool = False
    owner: str = ''
    scopes: List[FeatureFlagScopeSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class ScopeInputSchema(BaseModel):
    scope_type: str
    scope_value: str
    is_active: bool = True

    @field_validator('scope_type')
    @classmethod
    def validate_scope_type(cls, v: str) -> str:
        try:
            return ScopeType(v).value
        except ValueError:
            raise ValueError(
                f"Invalid scope_type '{v}'. "
                f"Valid: {', '.join(s.value for s in ScopeType)}."
            )

    @field_validator('scope_value')
    @classmethod
    def validate_scope_value(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError('scope_value must not be empty')
        if len(value) > 255:
            raise ValueError('scope_value must be at most 255 characters')
        return value


class CreateFeatureFlagSchema(BaseModel):
    key: str
    name: str
    description: str = ''
    flag_type: str = FlagType.RELEASE.value
    status: str = FlagStatus.DRAFT.value
    enabled: bool = False
    owner: str = ''
    scopes: List[ScopeInputSchema] = Field(default_factory=list)

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        key = v.strip()
        if not (3 <= len(key) <= 100):
            raise ValueError('key must be between 3 and 100 characters')
        if not _KEY_RE.match(key):
            raise ValueError(
                'key must be dotted lowercase segments '
                '(e.g. picking.route_v2)'
            )
        return key

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not (3 <= len(name) <= 120):
            raise ValueError('name must be between 3 and 120 characters')
        return name

    @field_validator('flag_type')
    @classmethod
    def validate_flag_type(cls, v: str) -> str:
        try:
            return FlagType(v).value
        except ValueError:
            raise ValueError(
                f"Invalid flag_type '{v}'. "
                f"Valid: {', '.join(t.value for t in FlagType)}."
            )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        try:
            return FlagStatus(v).value
        except ValueError:
            raise ValueError(
                f"Invalid status '{v}'. "
                f"Valid: {', '.join(s.value for s in FlagStatus)}."
            )


class UpdateFeatureFlagSchema(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    flag_type: Optional[str] = None
    status: Optional[str] = None
    enabled: Optional[bool] = None
    owner: Optional[str] = None
    scopes: Optional[List[ScopeInputSchema]] = None

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        key = v.strip()
        if not (3 <= len(key) <= 100):
            raise ValueError('key must be between 3 and 100 characters')
        if not _KEY_RE.match(key):
            raise ValueError(
                'key must be dotted lowercase segments '
                '(e.g. picking.route_v2)'
            )
        return key

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        name = v.strip()
        if not (3 <= len(name) <= 120):
            raise ValueError('name must be between 3 and 120 characters')
        return name

    @field_validator('flag_type')
    @classmethod
    def validate_flag_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            return FlagType(v).value
        except ValueError:
            raise ValueError(
                f"Invalid flag_type '{v}'. "
                f"Valid: {', '.join(t.value for t in FlagType)}."
            )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            return FlagStatus(v).value
        except ValueError:
            raise ValueError(
                f"Invalid status '{v}'. "
                f"Valid: {', '.join(s.value for s in FlagStatus)}."
            )
