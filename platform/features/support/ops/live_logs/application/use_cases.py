"""Use cases for the admin live-logs stream."""

from __future__ import annotations

from platform.features.support.ops.live_logs.domain.catalog import (
    LEVEL_CHOICES,
    LIVE_LOG_CHANNELS,
)
from platform.features.support.ops.live_logs.domain.interfaces import ILiveLogRingBuffer
from platform.features.support.ops.live_logs.domain.schemas import (
    LiveLogChannelView,
    LiveLogChannelsResult,
    LiveLogRecentResult,
)


class ListLiveLogChannelsUseCase:
    def execute(self) -> LiveLogChannelsResult:
        items = [
            LiveLogChannelView(
                key=c.key,
                label=c.label,
                icon=c.icon,
                description=c.description,
                logger=c.logger_name,
            )
            for c in LIVE_LOG_CHANNELS
        ]
        return LiveLogChannelsResult(items=items, levels=list(LEVEL_CHOICES))


class GetRecentLiveLogsUseCase:
    def __init__(self, ring: ILiveLogRingBuffer):
        self._ring = ring

    def execute(
        self,
        *,
        channel: str | None = None,
        min_level: str | None = None,
        limit: int = 100,
    ) -> LiveLogRecentResult:
        items = self._ring.recent(
            channel=channel or None,
            min_level=min_level or None,
            limit=limit,
        )
        return LiveLogRecentResult(items=items, returned=len(items))
