"""Contratos Pydantic del lado público (admin outbox + resource types).

``Audience`` y ``RecipientGroup`` son los value-objects que viajan entre el
resolver de audiencia y el fan-out; ``RecipientGroup`` agrupa destinatarios
por schema de tenant para que el dispatcher pueda enrutar con
``schema_context``.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from platform.features.communication.messaging.inbox.domain.enums import (
    AudienceScope,
    NotificationLevel,
    OutboxStatus,
)


# ── Value objects de audiencia ───────────────────────────────────────────────

class Audience(BaseModel):
    """A quién va dirigido un envío del administrador."""
    scope: AudienceScope
    target_company_id: Optional[uuid.UUID] = None
    target_user_id: Optional[uuid.UUID] = None


class RecipientGroup(BaseModel):
    """Destinatarios resueltos dentro de un único schema de tenant."""
    schema_name: str
    user_ids: List[uuid.UUID]


# ── Entrada del caso de uso de envío admin ───────────────────────────────────

class AdminNotifyInput(BaseModel):
    """Datos para crear una notificación de administrador."""
    admin_id: uuid.UUID
    admin_label: str
    title: str = Field(min_length=1, max_length=200)
    body: str = ''
    level: NotificationLevel = NotificationLevel.INFO
    audience: Audience


# ── Salidas ──────────────────────────────────────────────────────────────────

class OutboxItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_id: uuid.UUID
    admin_label: str
    scope: AudienceScope
    target_company_id: Optional[uuid.UUID] = None
    target_user_id: Optional[uuid.UUID] = None
    title: str
    body: str
    level: str
    status: OutboxStatus
    recipients_count: int
    error_detail: str = ''
    created_at: datetime
    dispatched_at: Optional[datetime] = None


# ── Resource types ───────────────────────────────────────────────────────────

class ResourceTypeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    label: str
    icon: str = ''
    route_template: str = ''
    is_active: bool


class CreateResourceTypeSchema(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    icon: str = ''
    route_template: str = ''
    is_active: bool = True


class UpdateResourceTypeSchema(BaseModel):
    label: Optional[str] = Field(default=None, max_length=120)
    icon: Optional[str] = None
    route_template: Optional[str] = None
    is_active: Optional[bool] = None


# ── Campanita del portal admin ───────────────────────────────────────────────

class AdminInboxPayload(BaseModel):
    """Contenido a materializar en la campanita de administradores."""
    title: str = Field(min_length=1, max_length=200)
    body: str = ''
    level: NotificationLevel = NotificationLevel.INFO
    kind: str = 'SYSTEM'
    actor_kind: str = 'SYSTEM'
    actor_label: str = 'Base'
    actor_id: Optional[uuid.UUID] = None
    resource_type_code: str = ''
    resource_id: Optional[uuid.UUID] = None
    resource_route: str = ''


class AdminInboxItem(BaseModel):
    """Fila de la campanita admin: destinatario + notificación."""
    id: uuid.UUID
    notification_id: uuid.UUID
    kind: str
    actor_kind: str
    actor_label: str
    title: str
    body: str
    level: NotificationLevel
    resource_type_code: str = ''
    resource_id: Optional[uuid.UUID] = None
    resource_route: str = ''
    read_at: Optional[datetime] = None
    created_at: datetime
