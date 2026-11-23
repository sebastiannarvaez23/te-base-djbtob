"""Adaptador ORM del inbox tenant.

Todas las consultas corren contra el schema ACTIVO (lo garantiza
django-tenants en peticiones HTTP, o ``schema_context`` en el fan-out).
"""

import uuid
from typing import List, Optional, Tuple

from django.utils import timezone

from client.features.communication.messaging.inbox.domain.enums import ReadStatus
from client.features.communication.messaging.inbox.domain.interfaces import INotificationRepository
from client.features.communication.messaging.inbox.domain.schemas import (
    NotificationOut,
    NotificationPayload,
)
from client.features.communication.messaging.inbox.models import (
    Notification,
    NotificationRecipient,
)
from platform.features.communication.messaging.inbox.models import NotificationResourceType


def _to_out(recipient: NotificationRecipient, route_by_code: dict) -> NotificationOut:
    n = recipient.notification
    return NotificationOut(
        id=recipient.id,
        notification_id=n.id,
        kind=n.kind,
        actor_kind=n.actor_kind,
        actor_label=n.actor_label,
        title=n.title,
        body=n.body,
        level=n.level,
        resource_type_code=n.resource_type_code,
        resource_id=n.resource_id,
        resource_route=route_by_code.get(n.resource_type_code, ''),
        read_at=recipient.read_at,
        created_at=recipient.created_at,
    )


class DjangoNotificationRepository(INotificationRepository):

    def create_notification(self, payload: NotificationPayload) -> uuid.UUID:
        obj = Notification.objects.create(
            kind=payload.kind.value,
            origin_id=payload.origin_id,
            actor_kind=payload.actor_kind.value,
            actor_id=payload.actor_id,
            actor_label=payload.actor_label,
            title=payload.title,
            body=payload.body,
            level=payload.level.value,
            resource_type_code=payload.resource_type_code,
            resource_id=payload.resource_id,
        )
        return obj.id

    def add_recipients(self, notification_id: uuid.UUID, user_ids: List[uuid.UUID]) -> int:
        rows = [
            NotificationRecipient(notification_id=notification_id, user_id=uid)
            for uid in dict.fromkeys(user_ids)  # de-dup conservando orden
        ]
        created = NotificationRecipient.objects.bulk_create(rows, ignore_conflicts=True)
        return len(created)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        status: ReadStatus,
        limit: int,
        offset: int,
    ) -> Tuple[List[NotificationOut], int]:
        qs = (
            NotificationRecipient.objects
            .select_related('notification')
            .filter(user_id=user_id, archived_at__isnull=True)
        )
        if status == ReadStatus.UNREAD:
            qs = qs.filter(read_at__isnull=True)
        elif status == ReadStatus.READ:
            qs = qs.filter(read_at__isnull=False)

        qs = qs.order_by('-created_at')
        total = qs.count()
        rows = list(qs[offset: offset + limit])

        # Resuelve las rutas de los tipos de recurso presentes en la página
        # (1 query; el registro vive en el schema público, visible desde el tenant).
        codes = {r.notification.resource_type_code for r in rows if r.notification.resource_type_code}
        route_by_code = (
            dict(
                NotificationResourceType.objects
                .filter(code__in=codes)
                .values_list('code', 'route_template')
            )
            if codes else {}
        )
        return [_to_out(r, route_by_code) for r in rows], total

    def unread_count(self, user_id: uuid.UUID) -> int:
        return NotificationRecipient.objects.filter(
            user_id=user_id, read_at__isnull=True, archived_at__isnull=True,
        ).count()

    def mark_read(self, user_id: uuid.UUID, recipient_id: Optional[uuid.UUID]) -> int:
        qs = NotificationRecipient.objects.filter(user_id=user_id, read_at__isnull=True)
        if recipient_id is not None:
            qs = qs.filter(id=recipient_id)
        return qs.update(read_at=timezone.now())

    def archive(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        return NotificationRecipient.objects.filter(
            user_id=user_id, id=recipient_id, archived_at__isnull=True,
        ).update(archived_at=timezone.now())
