"""Dispatcher de fan-out: enruta por schema y delega la escritura al manager.

SRP: el resolver decide *a quién* (grupos por schema); este dispatcher
decide *en qué schema* entrar; el manager *materializa y publica*. El
dispatcher es lo único que conoce ``schema_context``.
"""

from typing import List

from django_tenants.utils import schema_context

from client.features.communication.messaging.inbox.facade.manager import NotificationManager
from client.features.communication.messaging.inbox.domain.schemas import NotificationPayload
from platform.features.communication.messaging.inbox.domain.schemas import RecipientGroup


class FanoutDispatcher:

    def __init__(self, manager: NotificationManager):
        self.manager = manager

    def dispatch(self, payload: NotificationPayload, groups: List[RecipientGroup]) -> int:
        total = 0
        for group in groups:
            with schema_context(group.schema_name):
                total += self.manager.deliver(group.schema_name, payload, group.user_ids)
        return total
