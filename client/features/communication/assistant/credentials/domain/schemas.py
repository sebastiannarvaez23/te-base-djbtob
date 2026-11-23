from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProviderName = Literal['openai', 'anthropic']


class CreateCredentialSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    provider: ProviderName
    api_key: str = Field(min_length=8, max_length=512)
    label: str = Field(default='', max_length=120)
    activate: bool = True
    created_by: Optional[UUID] = None


class UpdateCredentialSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    api_key: Optional[str] = Field(default=None, min_length=8, max_length=512)
    label: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None

    @model_validator(mode='after')
    def at_least_one_field(self):
        if self.api_key is None and self.label is None and self.is_active is None:
            raise ValueError('At least one of api_key, label, is_active is required.')
        return self


class CredentialPublicSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: UUID
    provider: str
    label: str
    key_last4: str
    is_active: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ActiveByokSchema(BaseModel):
    """Clave descifrada para el ModelLayer (nunca sale por HTTP)."""

    model_config = ConfigDict(extra='forbid')

    provider: str
    api_key: str
    credential_id: UUID
