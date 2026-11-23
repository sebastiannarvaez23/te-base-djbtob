from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConnectionSchema(BaseModel):
    id: uuid.UUID
    connector_key: str
    name: str
    environment: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str
    schedule_cron: str = ''
    last_sync_at: Optional[datetime] = None
    last_error: str = ''
    created_by: Optional[int] = None
    secret_id: Optional[uuid.UUID] = None

    model_config = {'from_attributes': True}


class CreateConnectionSchema(BaseModel):
    connector_key: str
    name: str
    environment: str
    config: dict[str, Any] = Field(default_factory=dict)
    schedule_cron: str = ''
    secrets: dict[str, str] = Field(default_factory=dict)
    created_by: Optional[int] = None


class UpdateConnectionSchema(BaseModel):
    name: Optional[str] = None
    environment: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    schedule_cron: Optional[str] = None
    secrets: Optional[dict[str, str]] = None


class FieldMappingSchema(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    entity: str
    direction: str
    rules: list[dict[str, Any]]
    is_active: bool

    model_config = {'from_attributes': True}


class CreateFieldMappingSchema(BaseModel):
    connection_id: uuid.UUID
    entity: str = 'order'
    direction: str
    rules: list[dict[str, Any]]
    is_active: bool = True


class UpdateFieldMappingSchema(BaseModel):
    rules: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class SyncRunSchema(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    entity: str
    direction: str
    status: str
    stats: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    error_message: str = ''
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class OrderIntegrationSchema(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    external_id: str
    reference: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sync_status: str
    last_sync_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateOrderFromIntegrationSchema(BaseModel):
    connection_id: uuid.UUID
    external_id: str
    reference: str = ''
    status: str = 'DRAFT'
    payload: dict[str, Any] = Field(default_factory=dict)
