"""Inbox (campanita) + tenant user lookup. Schema-safe for Celery workers."""
import logging
import uuid

from django_tenants.utils import schema_context

from client.features.communication.messaging.inbox.domain.enums import ActorKind, NotificationKind
from client.features.communication.messaging.inbox.domain.schemas import NotificationPayload
from client.features.communication.messaging.inbox.facade.factory import NotificationManagerFactory
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel

from ..domain.interfaces import ICompanyRecipientLookup, IRefundNotifier
from ..domain.schemas import RefundNotification

logger = logging.getLogger('billing.refund')


class DjangoCompanyRecipientLookup(ICompanyRecipientLookup):
    def active_user_ids(self, schema_name: str) -> list[uuid.UUID]:
        from client.features.security.lifecycle.registration.models import User
        with schema_context(schema_name):
            return list(User.objects.filter(is_active=True).values_list('id', flat=True))


class InboxRefundNotifier(IRefundNotifier):
    def __init__(self, manager_factory=NotificationManagerFactory):
        self._manager_factory = manager_factory

    def notify(self, message: RefundNotification, user_ids: list[uuid.UUID]) -> None:
        if not user_ids:
            return
        payload = NotificationPayload(
            kind=NotificationKind.ADMIN_COMPANY,
            actor_kind=ActorKind.SYSTEM,
            actor_label='Facturación',
            title=message.title,
            body=message.body,
            level=NotificationLevel(message.level),
            resource_id=message.ticket_id,
        )
        with schema_context(message.schema_name):
            self._manager_factory.create().deliver(
                message.schema_name, payload, user_ids,
            )
