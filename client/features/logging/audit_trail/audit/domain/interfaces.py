from abc import ABC, abstractmethod

from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema
from client.features.logging.facade.context import LogContext


class IAuditLogRepository(ABC):
    """Port: persiste acciones de auditoría sobre entidades del sistema."""

    @abstractmethod
    def save(self, context: LogContext, data: AuditLogInputSchema) -> None:
        ...

    @abstractmethod
    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        ...
