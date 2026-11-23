import uuid
from abc import ABC, abstractmethod
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.functionalities.domain.schemas import (
    AssignFunctionalitySchema,
    CreateFunctionalitySchema,
    FunctionalitySchema,
    UpdateFunctionalitySchema,
)


class IFunctionalityRepository(ABC):

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def get_by_id(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]: ...

    @abstractmethod
    def create(self, data: CreateFunctionalitySchema) -> FunctionalitySchema: ...

    @abstractmethod
    def update(self, functionality_id: uuid.UUID, data: UpdateFunctionalitySchema) -> Optional[FunctionalitySchema]: ...

    @abstractmethod
    def delete(self, functionality_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def toggle(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]: ...

    @abstractmethod
    def assign_module(self, functionality_id: uuid.UUID, data: AssignFunctionalitySchema) -> Optional[FunctionalitySchema]: ...
