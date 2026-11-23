from abc import ABC, abstractmethod

from client.features.logging.facade.context import LogContext
from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema


class ISecurityLogRepository(ABC):
    """Port: persiste eventos de seguridad (login, permisos, etc)."""

    @abstractmethod
    def save(self, context: LogContext, data: SecurityLogInputSchema) -> None:
        ...

    @abstractmethod
    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        ...
