"""Factory que resuelve las dependencias concretas del NotificationManager."""

from core.realtime.publisher import RealtimePublisherFactory

from client.features.communication.messaging.inbox.facade.manager import NotificationManager
from client.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoNotificationRepository,
)
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoResourceTypeRepository,
)


class NotificationManagerFactory:

    @classmethod
    def create(cls) -> NotificationManager:
        return NotificationManager(
            repository=DjangoNotificationRepository(),
            resource_type_repo=DjangoResourceTypeRepository(),
            publisher=RealtimePublisherFactory.create(),
        )
