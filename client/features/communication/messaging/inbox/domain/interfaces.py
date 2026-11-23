"""Puerto del inbox tenant (opera SIEMPRE en el schema activo)."""

import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from client.features.communication.messaging.inbox.domain.enums import ReadStatus
from client.features.communication.messaging.inbox.domain.schemas import (
    NotificationOut,
    NotificationPayload,
)


class INotificationRepository(ABC):

    @abstractmethod
    def create_notification(self, payload: NotificationPayload) -> uuid.UUID:
        ...

    @abstractmethod
    def add_recipients(self, notification_id: uuid.UUID, user_ids: List[uuid.UUID]) -> int:
        ...

    @abstractmethod
    def list_for_user(
        self,
        user_id: uuid.UUID,
        status: ReadStatus,
        limit: int,
        offset: int,
    ) -> Tuple[List[NotificationOut], int]:
        """Devuelve (items, total)."""
        ...

    @abstractmethod
    def unread_count(self, user_id: uuid.UUID) -> int:
        ...

    @abstractmethod
    def mark_read(self, user_id: uuid.UUID, recipient_id: Optional[uuid.UUID]) -> int:
        """``recipient_id=None`` marca todas las no leídas. Devuelve filas afectadas."""
        ...

    @abstractmethod
    def archive(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        ...
