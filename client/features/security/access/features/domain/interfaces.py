from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from client.features.security.access.features.domain.schemas import (
    CreateFeatureSchema, FeatureSchema, UpdateFeatureSchema,
)


class IFeatureRepository(ABC):
    @abstractmethod
    def get_all(self, module: Optional[str] = None) -> list[FeatureSchema]: ...

    @abstractmethod
    def get_by_id(self, feature_id: UUID) -> Optional[FeatureSchema]: ...

    @abstractmethod
    def create(self, data: CreateFeatureSchema) -> FeatureSchema: ...

    @abstractmethod
    def update(self, feature_id: UUID, data: UpdateFeatureSchema) -> Optional[FeatureSchema]: ...
