from typing import Optional
from uuid import UUID

from platform.features.security.access.sections.domain.interfaces import ISectionRepository
from platform.features.security.access.sections.domain.schemas import (
    CreateSectionSchema, SectionSchema, UpdateSectionSchema,
)
from core.trace import trace_layer


class ListSectionsUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> list[SectionSchema]:
        return self.repository.get_all(filters=filters)


class GetSectionUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: UUID) -> Optional[SectionSchema]:
        return self.repository.get_by_id(section_id)


class CreateSectionUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateSectionSchema) -> SectionSchema:
        return self.repository.create(data)


class UpdateSectionUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: UUID, data: UpdateSectionSchema) -> Optional[SectionSchema]:
        return self.repository.update(section_id, data)


class DeleteSectionUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: UUID) -> bool:
        return self.repository.delete(section_id)


class ReorderSectionsUseCase:
    def __init__(self, repository: ISectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, ids: list[UUID]) -> int:
        return self.repository.reorder(ids)
