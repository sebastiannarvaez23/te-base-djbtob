from abc import ABC, abstractmethod

from client.features.logging.facade.context import LogContext
from client.features.logging.system.system.domain.schemas import SystemLogSchema


class ISystemLogHandler(ABC):
    """Port: emite logs de eventos del sistema (startup, scheduler, migrations, etc)."""

    @abstractmethod
    def emit(self, context: LogContext, data: SystemLogSchema) -> None:
        ...
