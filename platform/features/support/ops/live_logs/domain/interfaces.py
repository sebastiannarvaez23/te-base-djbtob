from __future__ import annotations

from abc import ABC, abstractmethod

from platform.features.support.ops.live_logs.domain.schemas import LiveLogLineView


class ILiveLogRingBuffer(ABC):
    """Anillo Redis de las últimas N líneas para catch-up al conectar."""

    @abstractmethod
    def append(self, line: LiveLogLineView) -> None:
        ...

    @abstractmethod
    def recent(
        self,
        *,
        channel: str | None = None,
        min_level: str | None = None,
        limit: int = 100,
    ) -> list[LiveLogLineView]:
        ...
