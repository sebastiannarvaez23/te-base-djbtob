from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from platform.features.security.access.sections.domain.schemas import (
    CreateSectionSchema, SectionSchema, UpdateSectionSchema,
)


class ISectionRepository(ABC):
    @abstractmethod
    def get_all(self, filters: dict | None = None) -> list[SectionSchema]: ...

    @abstractmethod
    def get_by_id(self, section_id: UUID) -> Optional[SectionSchema]: ...

    @abstractmethod
    def create(self, data: CreateSectionSchema) -> SectionSchema: ...

    @abstractmethod
    def update(self, section_id: UUID, data: UpdateSectionSchema) -> Optional[SectionSchema]: ...

    @abstractmethod
    def delete(self, section_id: UUID) -> bool: ...

    @abstractmethod
    def reorder(self, ids: list[UUID]) -> int: ...
