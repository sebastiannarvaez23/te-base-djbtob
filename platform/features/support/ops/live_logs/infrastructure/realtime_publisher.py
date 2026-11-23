"""Realtime publisher for live log lines."""

from __future__ import annotations

from platform.features.support.ops.live_logs.domain.schemas import LiveLogLineView
from platform.features.support.ops.live_logs.infrastructure.redis_ring import (
    live_log_subscriber_count,
)
from core.realtime import RealtimeMessage, RealtimePublisherFactory
from core.realtime.groups import RealtimeGroups


class LiveLogsRealtimePublisher:
    """Pushes structured log lines to the admin live-logs group."""

    def __init__(self, publisher=None):
        self._publisher = publisher or RealtimePublisherFactory.create()

    def emit_line(self, line: LiveLogLineView) -> None:
        if live_log_subscriber_count() <= 0:
            return
        self._publisher.to_group(
            RealtimeGroups.platform_live_logs(),
            RealtimeMessage(
                type='log.line',
                payload=line.model_dump(mode='json'),
            ),
        )
