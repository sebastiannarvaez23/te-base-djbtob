"""Contratos Pydantic del inbox tenant."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from client.features.communication.messaging.inbox.domain.enums import (
    ActorKind,
    NotificationKind,
)
# El nivel es un concepto común; se reutiliza el enum del lado público
# (dirección de dependencia permitida client → platform).
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel


class NotificationPayload(BaseModel):
    """Todo lo necesario para materializar una ``Notification`` en un schema."""
    kind: NotificationKind
    actor_kind: ActorKind
    actor_label: str
    title: str = Field(min_length=1, max_length=200)
    body: str = ''
    level: NotificationLevel = NotificationLevel.INFO
    actor_id: Optional[uuid.UUID] = None
    origin_id: Optional[uuid.UUID] = None
    resource_type_code: str = ''
    resource_id: Optional[uuid.UUID] = None


class ShareInput(BaseModel):
    """Entrada del caso de uso 'compartir un elemento' (escenario 1)."""
    resource_type_code: str = Field(min_length=1, max_length=80)
    resource_id: uuid.UUID
    recipient_user_ids: List[uuid.UUID] = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    body: str = ''
    level: NotificationLevel = NotificationLevel.INFO


class NotificationOut(BaseModel):
    """Lo que la campanita muestra: la fila de destinatario + su notificación."""
    id: uuid.UUID                 # id del NotificationRecipient (para marcar leído)
    notification_id: uuid.UUID
    kind: str
    actor_kind: str
    actor_label: str
    title: str
    body: str
    level: str
    resource_type_code: str = ''
    resource_id: Optional[uuid.UUID] = None
    # Plantilla de ruta del tipo de recurso (ej. '/warehouse/pickings/:id'),
    # resuelta desde el registro público; permite el deep-link sin hardcodear
    # rutas en el frontend. Vacía si no aplica o el tipo fue desactivado.
    resource_route: str = ''
    read_at: Optional[datetime] = None
    created_at: datetime
