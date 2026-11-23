"""Casos de uso de LECTURA del inbox (la campanita).

La emisión (compartir / entregar) va por el facade ``NotificationManager``,
que es el punto reutilizable cross-feature. Aquí viven las operaciones que
solo consume el propio dueño de la campanita.

Todas filtran SIEMPRE por ``user_id`` → aislamiento por usuario.
"""

import uuid
from typing import List, Optional, Tuple

from client.features.communication.messaging.inbox.domain.enums import ReadStatus
from client.features.communication.messaging.inbox.domain.interfaces import INotificationRepository
from client.features.communication.messaging.inbox.domain.schemas import NotificationOut
from core.trace import trace_layer


class ListInboxUseCase:
    def __init__(self, repository: INotificationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, user_id: uuid.UUID, status: ReadStatus, limit: int, offset: int,
    ) -> Tuple[List[NotificationOut], int]:
        return self.repository.list_for_user(user_id, status, limit, offset)


class GetUnreadCountUseCase:
    def __init__(self, repository: INotificationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> int:
        return self.repository.unread_count(user_id)


class MarkNotificationReadUseCase:
    def __init__(self, repository: INotificationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        return self.repository.mark_read(user_id, recipient_id)


class MarkAllReadUseCase:
    def __init__(self, repository: INotificationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> int:
        return self.repository.mark_read(user_id, None)


class ArchiveNotificationUseCase:
    def __init__(self, repository: INotificationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        return self.repository.archive(user_id, recipient_id)
