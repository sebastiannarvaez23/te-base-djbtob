from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from .schemas import HandbookChangeRequestSchema


class IChangeRequestRepository(ABC):
    """Persistencia de solicitudes. Apply/discard de bytes lo hace el adapter."""

    @abstractmethod
    def get(self, request_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        ...

    @abstractmethod
    def get_pending_for_page(self, page_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        ...

    @abstractmethod
    def save(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        ...

    @abstractmethod
    def approve(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        """Publica la versión de trabajo y guarda la resolución en una sola transacción."""

    @abstractmethod
    def reject(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        """Descarta la versión de trabajo y guarda la resolución en una sola transacción."""

    @abstractmethod
    def list_pending(self, *, offset: int = 0, limit: int = 20) -> tuple[list[HandbookChangeRequestSchema], int]:
        """Pendientes más recientes primero, con el nombre de quien propone."""
