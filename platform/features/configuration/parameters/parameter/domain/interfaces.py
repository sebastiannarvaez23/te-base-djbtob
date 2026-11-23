import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import CreateParameterSchema, ParameterSchema, UpdateParameterSchema


class IParameterRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[ParameterSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[ParameterSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[ParameterSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateParameterSchema) -> ParameterSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateParameterSchema) -> Optional[ParameterSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
