from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConnectorDefinitionSchema(BaseModel):
    id: uuid.UUID
    key: str
    kind: str
    name: str
    description: str = ''
    version: str = '1.0'
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    model_config = {'from_attributes': True}


class CreateConnectorDefinitionSchema(BaseModel):
    key: str
    kind: str
    name: str
    description: str = ''
    version: str = '1.0'
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class UpdateConnectorDefinitionSchema(BaseModel):
    kind: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[list[str]] = None
    config_schema: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
