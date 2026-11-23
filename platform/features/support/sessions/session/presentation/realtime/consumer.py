from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups


class ClientSupportSessionConsumer(BaseRealtimeConsumer):
    """Tenant user channel for support session events."""

    async def connect(self):
        if self.scope.get('audience') == 'admin':
            await self.close(code=4401)
            return
        await super().connect()

    def get_groups(self) -> list[str]:
        return [RealtimeGroups.user(self.schema, self.user.id)]


class AdminSupportSessionConsumer(BaseRealtimeConsumer):
    """Platform admin channel for assigned support session + queue board events."""

    async def connect(self):
        if self.scope.get('audience') != 'admin':
            await self.close(code=4401)
            return
        await super().connect()

    def get_groups(self) -> list[str]:
        return [
            RealtimeGroups.user(self.schema, self.user.id),
            RealtimeGroups.platform_support(),
        ]
