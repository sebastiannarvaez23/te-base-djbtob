"""Schemas Pydantic del dominio de integraciones."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import (
    ConnectorKind,
    ConnectorProvider,
    Environment,
    SyncDirection,
    SyncStatus,
)


class ConnectionProfile(BaseModel):
    """Perfil de conexión en memoria (Fase 2 lo persiste en BD tenant)."""

    connection_id: UUID
    tenant_schema: str
    provider: ConnectorProvider
    kind: ConnectorKind
    environment: Environment
    connector_version: str = '1.0'
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class ExternalEntityRef(BaseModel):
    entity: str
    external_id: str
    internal_id: Optional[str] = None


class OperationContext(BaseModel):
    """Contexto de ejecución para el runner (logging, idempotencia, circuit breaker)."""

    connection_id: UUID
    tenant_schema: str
    operation: str
    request_id: str = '-'
    idempotency_key: Optional[str] = None
    user_id: Optional[int] = None
    warehouse_id: Optional[int] = None


class SyncRequest(BaseModel):
    profile: ConnectionProfile
    entity: str
    direction: SyncDirection
    dry_run: bool = False
    cursor: Optional[str] = None
    limit: int = 100
    payload: Optional[dict[str, Any]] = None


class SyncEntityResult(BaseModel):
    external_ref: ExternalEntityRef
    action: str
    success: bool = True
    error: Optional[str] = None


class SyncResult(BaseModel):
    status: SyncStatus
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    warnings: list[str] = Field(default_factory=list)
    entities: list[SyncEntityResult] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    degraded: bool = False


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str = ''
    latency_ms: int = 0


class DryRunResult(BaseModel):
    would_create: int = 0
    would_update: int = 0
    would_skip: int = 0
    preview: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    kept: str
    field: str
    inbound_value: Any = None
    wms_value: Any = None
    warning: str = ''


class BatchSyncResult(BaseModel):
    pull: Optional[SyncResult] = None
    push: Optional[SyncResult] = None
