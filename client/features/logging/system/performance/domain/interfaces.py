from abc import ABC, abstractmethod

from client.features.logging.facade.context import LogContext
from client.features.logging.system.performance.domain.schemas import PerformanceLogSchema


class IPerformanceLogHandler(ABC):
    """Port: emite métricas de performance al sistema de monitoreo (APM)."""

    @abstractmethod
    def emit(self, context: LogContext, data: PerformanceLogSchema) -> None:
        ...
