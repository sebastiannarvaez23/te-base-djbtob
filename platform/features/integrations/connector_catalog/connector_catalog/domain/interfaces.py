import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import (
    ConnectorDefinitionSchema,
    CreateConnectorDefinitionSchema,
    UpdateConnectorDefinitionSchema,
)


class IConnectorCatalogRepository(ABC):

    @abstractmethod
    def get_all(self, *, active_only: bool = False) -> List[ConnectorDefinitionSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[ConnectorDefinitionSchema]:
        ...

    @abstractmethod
    def get_by_key(self, key: str) -> Optional[ConnectorDefinitionSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateConnectorDefinitionSchema) -> ConnectorDefinitionSchema:
        ...

    @abstractmethod
    def update(
        self, id: uuid.UUID, data: UpdateConnectorDefinitionSchema,
    ) -> Optional[ConnectorDefinitionSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
