from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from core.ai.model_layer.catalog import AI_CAPABILITIES, AI_CHAT_PROVIDERS

# Capacidades gestionables en el control plane (excluye chat — vive en assistant).
CONTROL_CAPABILITIES = tuple(
    c for c in AI_CAPABILITIES if c not in ('chat',)
)


class CapabilityStubSchema(BaseModel):
    key: str
    enabled: bool = False
    provider: str = 'fake'
    notes: str = ''
    runtime_health: str = 'unknown'

    @field_validator('key')
    @classmethod
    def key_ok(cls, value: str) -> str:
        key = (value or '').strip().lower()
        if key not in CONTROL_CAPABILITIES:
            raise ValueError(f'Unknown capability: {value}')
        return key

    @field_validator('provider')
    @classmethod
    def provider_ok(cls, value: str) -> str:
        name = (value or 'fake').lower()
        if name not in AI_CHAT_PROVIDERS:
            raise ValueError(f'Invalid stub provider: {value}')
        return name


class CapabilityControlAdminSchema(BaseModel):
    id: Optional[UUID] = None
    capabilities: list[CapabilityStubSchema] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


def default_capabilities() -> list[CapabilityStubSchema]:
    return [
        CapabilityStubSchema(key=key, enabled=False, provider='fake', notes='')
        for key in CONTROL_CAPABILITIES
    ]
