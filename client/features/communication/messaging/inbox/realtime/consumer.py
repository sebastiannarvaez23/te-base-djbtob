"""Consumidor WS de la campanita.

Mínimo gracias a ``BaseRealtimeConsumer``: solo declara su grupo. El
``user`` y el ``schema`` los inyectan los middlewares ASGI.
"""

from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups


class NotificationConsumer(BaseRealtimeConsumer):
    def get_groups(self) -> list[str]:
        return [RealtimeGroups.user(self.schema, self.user.id)]
