"""
NotificationManager
────────────────────
Punto de entrada único para EMITIR notificaciones a la campanita desde
cualquier feature (warehouse, etc.), sin conocer internals.

Recibe puertos por constructor (DIP): el repositorio del inbox tenant, el
registro de tipos compartibles (público) y el publisher de tiempo real.
"""

import uuid
from typing import List

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException
from core.realtime.envelope import RealtimeMessage
from core.realtime.publisher import IRealtimePublisher

from client.features.communication.messaging.inbox.domain.context import NotificationContext
from client.features.communication.messaging.inbox.domain.enums import NotificationKind
from client.features.communication.messaging.inbox.domain.interfaces import INotificationRepository
from client.features.communication.messaging.inbox.domain.schemas import (
    NotificationPayload,
    ShareInput,
)
from platform.features.communication.messaging.inbox.domain.interfaces import IResourceTypeRepository


class NotificationManager:

    def __init__(
        self,
        repository: INotificationRepository,
        resource_type_repo: IResourceTypeRepository,
        publisher: IRealtimePublisher,
    ):
        self.repository = repository
        self.resource_type_repo = resource_type_repo
        self.publisher = publisher

    # ── API de intención ──────────────────────────────────────────────────────

    def share(self, context: NotificationContext, data: ShareInput, schema_name: str) -> int:
        """Escenario 1: un usuario comparte un elemento con su empresa.

        Se ejecuta dentro del schema activo del tenant; el elemento vive en
        ese mismo schema.
        """
        resource_type = self.resource_type_repo.get_by_code(data.resource_type_code)
        if resource_type is None:
            raise NotFoundException(AppErrorCode.NOTIF_RESOURCE_TYPE_NOT_FOUND)
        if not resource_type.is_active:
            raise ConflictException(AppErrorCode.NOTIF_RESOURCE_TYPE_INACTIVE)

        payload = NotificationPayload(
            kind=NotificationKind.SHARE,
            actor_kind=context.actor_kind,
            actor_id=context.actor_id,
            actor_label=context.actor_label,
            title=data.title,
            body=data.body,
            level=data.level,
            resource_type_code=data.resource_type_code,
            resource_id=data.resource_id,
        )
        return self._emit(schema_name, payload, data.recipient_user_ids)

    def deliver(self, schema_name: str, payload: NotificationPayload, user_ids: List[uuid.UUID]) -> int:
        """Escenario 2: materializa una notificación del admin en un schema.

        Usada por el fan-out, ya dentro de ``schema_context(schema_name)``.
        """
        return self._emit(schema_name, payload, user_ids)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _emit(self, schema_name: str, payload: NotificationPayload, user_ids: List[uuid.UUID]) -> int:
        notification_id = self.repository.create_notification(payload)
        count = self.repository.add_recipients(notification_id, user_ids)
        self._publish(schema_name, notification_id, payload, user_ids)
        return count

    def _publish(self, schema_name, notification_id, payload: NotificationPayload, user_ids) -> None:
        message = RealtimeMessage(
            type='notification.new',
            payload={
                'notification_id': str(notification_id),
                'kind': payload.kind.value,
                'title': payload.title,
                'body': payload.body,
                'level': payload.level.value,
                'actor_label': payload.actor_label,
                'resource_type_code': payload.resource_type_code,
                'resource_id': str(payload.resource_id) if payload.resource_id else None,
            },
        )
        for user_id in user_ids:
            self.publisher.to_user(schema_name, user_id, message)
