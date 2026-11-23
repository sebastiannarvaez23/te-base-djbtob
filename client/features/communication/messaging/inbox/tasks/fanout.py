"""
inbox.process_outbox_fanout
───────────────────────────
Consume un ``AdminNotificationOutbox`` (público), resuelve la audiencia y
materializa las notificaciones dentro de cada schema de tenant.

La plataforma encola esta tarea POR NOMBRE (``inbox.process_outbox_fanout``)
sin importar este módulo, manteniendo la dirección de dependencia
client → platform.
"""

import logging

from celery import shared_task

from client.features.communication.messaging.inbox.domain.enums import (
    ActorKind,
    NotificationKind,
)
from client.features.communication.messaging.inbox.domain.schemas import NotificationPayload
from client.features.communication.messaging.inbox.facade.factory import NotificationManagerFactory
from client.features.communication.messaging.inbox.infrastructure.fanout import FanoutDispatcher
from platform.features.communication.messaging.inbox.domain.enums import (
    AudienceScope,
    OutboxStatus,
)
from platform.features.communication.messaging.inbox.domain.schemas import Audience
from platform.features.communication.messaging.inbox.infrastructure.audience.resolvers import (
    AudienceResolverRegistry,
)
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoOutboxRepository,
)

logger = logging.getLogger('app.tasks')

_KIND_BY_SCOPE = {
    AudienceScope.SINGLE_USER: NotificationKind.ADMIN_DIRECT,
    AudienceScope.COMPANY_USERS: NotificationKind.ADMIN_COMPANY,
    AudienceScope.ALL_TENANTS: NotificationKind.ADMIN_BROADCAST,
}


def _payload_from_outbox(item) -> NotificationPayload:
    return NotificationPayload(
        kind=_KIND_BY_SCOPE[item.scope],
        actor_kind=ActorKind.ADMIN,
        actor_id=item.admin_id,
        actor_label=item.admin_label,
        origin_id=item.id,
        title=item.title,
        body=item.body,
        level=item.level,
    )


@shared_task(name='inbox.process_outbox_fanout', bind=True, max_retries=3, default_retry_delay=30)
def process_outbox_fanout(self, outbox_id: str):
    outbox_repo = DjangoOutboxRepository()
    item = outbox_repo.get(outbox_id)
    if item is None:
        logger.warning('fanout: outbox %s no existe; nada que hacer', outbox_id)
        return

    outbox_repo.set_status(item.id, OutboxStatus.DISPATCHING)
    try:
        payload = _payload_from_outbox(item)
        audience = Audience(
            scope=item.scope,
            target_company_id=item.target_company_id,
            target_user_id=item.target_user_id,
        )
        groups = AudienceResolverRegistry.default().resolve(audience)

        dispatcher = FanoutDispatcher(NotificationManagerFactory.create())
        count = dispatcher.dispatch(payload, groups)

        outbox_repo.set_status(item.id, OutboxStatus.SENT, recipients_count=count)
        logger.info('fanout: outbox %s entregado a %s destinatarios', outbox_id, count)
    except Exception as exc:
        outbox_repo.set_status(item.id, OutboxStatus.FAILED, error_detail=str(exc)[:500])
        logger.error('fanout: outbox %s falló: %s', outbox_id, exc)
        raise self.retry(exc=exc)
