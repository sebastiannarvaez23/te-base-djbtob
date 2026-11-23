import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import (
    AdminParameterTypeSchema,
    CreateAdminParameterTypeSchema,
    UpdateAdminParameterTypeSchema,
)


class IAdminParameterTypeRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[AdminParameterTypeSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[AdminParameterTypeSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[AdminParameterTypeSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateAdminParameterTypeSchema) -> AdminParameterTypeSchema:
        ...

    @abstractmethod
    def update(
        self, id: uuid.UUID, data: UpdateAdminParameterTypeSchema,
    ) -> Optional[AdminParameterTypeSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
