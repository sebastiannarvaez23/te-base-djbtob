import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import (
    AdminParameterSchema,
    CreateAdminParameterSchema,
    UpdateAdminParameterSchema,
)


class IAdminParameterRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[AdminParameterSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[AdminParameterSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[AdminParameterSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateAdminParameterSchema) -> AdminParameterSchema:
        ...

    @abstractmethod
    def update(
        self, id: uuid.UUID, data: UpdateAdminParameterSchema,
    ) -> Optional[AdminParameterSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def count_by_type(self, parameter_type_id: uuid.UUID) -> int:
        ...
