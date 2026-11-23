from asgiref.sync import sync_to_async

from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups
from platform.features.support.ops.live_logs.infrastructure.redis_ring import (
    decr_live_log_subscribers,
    incr_live_log_subscribers,
)


class LiveLogsConsumer(BaseRealtimeConsumer):
    """Admin-only push channel for structured live log lines."""

    def get_groups(self) -> list[str]:
        return [RealtimeGroups.platform_live_logs()]

    async def connect(self):
        if self.scope.get('audience') != 'admin':
            await self.close(code=4401)
            return
        await super().connect()
        if getattr(self, 'channel_name', None):
            await sync_to_async(incr_live_log_subscribers, thread_sensitive=True)()

    async def disconnect(self, code):
        if getattr(self, 'channel_name', None) and self.scope.get('audience') == 'admin':
            await sync_to_async(decr_live_log_subscribers, thread_sensitive=True)()
        await super().disconnect(code)
