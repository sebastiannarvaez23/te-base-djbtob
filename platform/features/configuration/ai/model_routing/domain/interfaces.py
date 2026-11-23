from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.ai.model_layer.schemas import ModelRoutingTable


class IModelRoutingRepository(ABC):

    @abstractmethod
    def get_table(self) -> ModelRoutingTable:
        ...

    @abstractmethod
    def save_table(self, table: ModelRoutingTable) -> ModelRoutingTable:
        ...

    @abstractmethod
    def get_updated_at(self) -> Optional[object]:
        ...
