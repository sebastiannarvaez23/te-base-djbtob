"""Consumidor WS de la campanita del portal admin."""

from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups


class AdminInboxConsumer(BaseRealtimeConsumer):
    """Empuja ``notification.new`` al AdminUser autenticado (schema public)."""

    async def connect(self):
        if self.scope.get('audience') != 'admin':
            await self.close(code=4401)
            return
        await super().connect()

    def get_groups(self) -> list[str]:
        return [RealtimeGroups.user(self.schema, self.user.id)]
