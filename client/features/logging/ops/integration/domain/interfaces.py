from abc import ABC, abstractmethod

from client.features.logging.facade.context import LogContext
from client.features.logging.ops.integration.domain.schemas import IntegrationLogInputSchema


class IIntegrationLogRepository(ABC):
    """Port: persiste eventos de integración con sistemas externos."""

    @abstractmethod
    def save(self, context: LogContext, data: IntegrationLogInputSchema) -> None:
        ...

    @abstractmethod
    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        ...
