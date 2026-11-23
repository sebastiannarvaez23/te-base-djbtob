import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.modules.domain.schemas import (
    ModuleSchema,
    CreateModuleSchema,
    UpdateModuleSchema,
)


class IModuleRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[ModuleSchema]: ...

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def get_by_id(self, module_id: uuid.UUID) -> Optional[ModuleSchema]: ...

    @abstractmethod
    def create(self, data: CreateModuleSchema) -> ModuleSchema: ...

    @abstractmethod
    def update(self, module_id: uuid.UUID, data: UpdateModuleSchema) -> Optional[ModuleSchema]: ...

    @abstractmethod
    def delete(self, module_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def toggle(self, module_id: uuid.UUID) -> Optional[ModuleSchema]: ...

    @abstractmethod
    def reorder(self, ids: list[uuid.UUID]) -> int: ...
