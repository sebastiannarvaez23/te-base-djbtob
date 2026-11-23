from abc import ABC, abstractmethod

from client.features.logging.system.errors.domain.schemas import ErrorLogSchema
from client.features.logging.facade.context import LogContext


class IErrorLogHandler(ABC):
    """Port: emite logs de error a sistemas externos (ELK / archivos)."""

    @abstractmethod
    def emit(self, context: LogContext, data: ErrorLogSchema) -> None:
        ...
