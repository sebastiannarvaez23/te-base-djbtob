import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import CreateParameterTypeSchema, ParameterTypeSchema, UpdateParameterTypeSchema


class IParameterTypeRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[ParameterTypeSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[ParameterTypeSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[ParameterTypeSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateParameterTypeSchema) -> ParameterTypeSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateParameterTypeSchema) -> Optional[ParameterTypeSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
