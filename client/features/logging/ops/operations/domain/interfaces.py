from abc import ABC, abstractmethod
from uuid import UUID

from client.features.logging.facade.context import LogContext
from client.features.logging.ops.operations.domain.schemas import (
    WarehouseEventInputSchema,
    WarehouseEventRecord,
)


class IWarehouseEventRepository(ABC):
    """Port: persiste eventos operativos del warehouse."""

    @abstractmethod
    def save(self, context: LogContext, data: WarehouseEventInputSchema) -> None:
        ...

    @abstractmethod
    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        ...

    @abstractmethod
    def list_for_reference(
        self,
        reference_id: UUID,
        reference_type: str | None,
        limit: int,
        warehouse_id: UUID | None = None,
    ) -> list[WarehouseEventRecord]:
        """Eventos del registro, del más reciente al más antiguo.

        Con ``warehouse_id`` suma los eventos de ese almacén que lo citan en ``refs``.
        """

    @abstractmethod
    def list_for_warehouse(
        self,
        warehouse_id: UUID,
        prefixes: tuple[str, ...],
        limit: int,
    ) -> list[WarehouseEventRecord]:
        """Eventos del almacén cuyo tipo empieza por alguno de ``prefixes``, del más reciente al más antiguo."""

    @abstractmethod
    def list_recent(self, event_types: tuple[str, ...], limit: int) -> list[WarehouseEventRecord]:
        """Hitos del tenant sin reintentos idempotentes, del más reciente al más antiguo."""


class IActorDirectory(ABC):
    """Port: nombre visible de quien ejecutó cada evento."""

    @abstractmethod
    def display_names(self, user_ids: set[UUID]) -> dict[UUID, str]:
        ...
