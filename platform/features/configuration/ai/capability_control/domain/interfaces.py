from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .schemas import CapabilityControlAdminSchema, CapabilityStubSchema


class ICapabilityControlRepository(ABC):

    @abstractmethod
    def get_all(self) -> list[CapabilityStubSchema]:
        ...

    @abstractmethod
    def save_all(self, items: list[CapabilityStubSchema]) -> list[CapabilityStubSchema]:
        ...

    @abstractmethod
    def get_updated_at(self) -> Optional[object]:
        ...
