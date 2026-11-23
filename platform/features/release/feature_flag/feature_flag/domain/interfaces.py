from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from core.flags.domain.schemas import FlagDefinition

from .schemas import (
    CreateFeatureFlagSchema,
    FeatureFlagSchema,
    UpdateFeatureFlagSchema,
)


class IFeatureFlagRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[FeatureFlagSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[FeatureFlagSchema]:
        ...

    @abstractmethod
    def get_by_key(self, key: str) -> Optional[FeatureFlagSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateFeatureFlagSchema) -> FeatureFlagSchema:
        ...

    @abstractmethod
    def update(
        self, id: uuid.UUID, data: UpdateFeatureFlagSchema,
    ) -> Optional[FeatureFlagSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def get_active_definitions(self) -> List[FlagDefinition]:
        """Snapshot evaluable: flags ACTIVE con sus scopes."""
        ...
