import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import (
    ConnectionSchema,
    CreateConnectionSchema,
    CreateFieldMappingSchema,
    CreateOrderFromIntegrationSchema,
    FieldMappingSchema,
    OrderIntegrationSchema,
    SyncRunSchema,
    UpdateConnectionSchema,
    UpdateFieldMappingSchema,
)


class IConnectionRepository(ABC):

    @abstractmethod
    def list_all(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[ConnectionSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateConnectionSchema, secret_ref_id: Optional[uuid.UUID]) -> ConnectionSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateConnectionSchema) -> Optional[ConnectionSchema]:
        ...

    @abstractmethod
    def update_health(
        self, id: uuid.UUID, *, status: str | None = None, last_error: str = '', last_sync_at=None,
    ) -> None:
        ...


class ISecretRepository(ABC):

    @abstractmethod
    def store_encrypted(self, scope: str, secrets: dict[str, str]) -> uuid.UUID:
        ...

    @abstractmethod
    def get_decrypted(self, secret_id: uuid.UUID) -> dict[str, str]:
        ...

    @abstractmethod
    def rotate(self, secret_id: uuid.UUID, scope: str, secrets: dict[str, str]) -> None:
        ...


class IFieldMappingRepository(ABC):

    @abstractmethod
    def list_by_connection(self, connection_id: uuid.UUID) -> List[FieldMappingSchema]:
        ...

    @abstractmethod
    def get_active(self, connection_id: uuid.UUID, entity: str, direction: str) -> Optional[FieldMappingSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateFieldMappingSchema) -> FieldMappingSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateFieldMappingSchema) -> Optional[FieldMappingSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...


class ISyncRunRepository(ABC):

    @abstractmethod
    def create(self, connection_id: uuid.UUID, entity: str, direction: str, *, dry_run: bool) -> SyncRunSchema:
        ...

    @abstractmethod
    def mark_running(self, id: uuid.UUID) -> None:
        ...

    @abstractmethod
    def finish(
        self, id: uuid.UUID, status: str, stats: dict, error_message: str = '',
    ) -> SyncRunSchema:
        ...

    @abstractmethod
    def list_recent(self, connection_id: uuid.UUID | None = None, limit: int = 50) -> List[SyncRunSchema]:
        ...


class IIntegrationOrderRepository(ABC):

    @abstractmethod
    def get_by_external_id(self, connection_id: uuid.UUID, external_id: str) -> Optional[OrderIntegrationSchema]:
        ...

    @abstractmethod
    def create_from_integration(self, data: CreateOrderFromIntegrationSchema) -> OrderIntegrationSchema:
        ...

    @abstractmethod
    def update_from_integration(self, order_id: uuid.UUID, **fields) -> OrderIntegrationSchema:
        ...

    @abstractmethod
    def list_pending_outbound(self, connection_id: uuid.UUID, limit: int = 100) -> List[OrderIntegrationSchema]:
        ...

    @abstractmethod
    def mark_synced(self, order_id: uuid.UUID) -> None:
        ...
