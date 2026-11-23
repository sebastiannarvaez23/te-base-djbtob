"""
Value object con la identidad del actor que origina una notificación.

Análogo a ``LogContext``: se construye desde el request en la capa de
presentación y viaja hacia el dominio sin acoplar a Django.
"""

import uuid
from typing import Optional

from pydantic import BaseModel

from client.features.communication.messaging.inbox.domain.enums import ActorKind


class NotificationContext(BaseModel):
    actor_kind: ActorKind
    actor_label: str
    actor_id: Optional[uuid.UUID] = None


class NotificationContextBuilder:

    @staticmethod
    def from_request(request) -> NotificationContext:
        user = getattr(request, 'user', None)
        label = ''
        actor_id = None
        if user is not None and getattr(user, 'is_authenticated', False):
            actor_id = user.pk
            full = f'{getattr(user, "first_name", "") or ""} {getattr(user, "last_name", "") or ""}'.strip()
            label = full or getattr(user, 'username', '')
        return NotificationContext(
            actor_kind=ActorKind.USER,
            actor_label=label or 'Usuario',
            actor_id=actor_id,
        )
