from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups


class TaskMonitorConsumer(BaseRealtimeConsumer):
    """Admin-only push channel for automated-task run/step events."""

    def get_groups(self) -> list[str]:
        return [RealtimeGroups.platform_task_monitor()]

    async def connect(self):
        # Only platform admins may subscribe (audience set by JWTAuthMiddleware).
        if self.scope.get('audience') != 'admin':
            await self.close(code=4401)
            return
        await super().connect()
