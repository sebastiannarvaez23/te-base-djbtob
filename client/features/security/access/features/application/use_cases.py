from typing import Optional
from uuid import UUID

from client.features.security.access.features.domain.interfaces import IFeatureRepository
from client.features.security.access.features.domain.schemas import (
    CreateFeatureSchema, FeatureSchema, UpdateFeatureSchema,
)
from core.trace import trace_layer


class ListFeaturesUseCase:
    def __init__(self, repository: IFeatureRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module: Optional[str] = None) -> list[FeatureSchema]:
        return self.repository.get_all(module=module)


class CreateFeatureUseCase:
    def __init__(self, repository: IFeatureRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateFeatureSchema) -> FeatureSchema:
        return self.repository.create(data)


class DeleteFeatureUseCase:
    def __init__(self, repository: IFeatureRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, feature_id: UUID) -> bool:
        return self.repository.delete(feature_id)


class UpdateFeatureUseCase:
    def __init__(self, repository: IFeatureRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, feature_id: UUID, data: UpdateFeatureSchema) -> Optional[FeatureSchema]:
        return self.repository.update(feature_id, data)
