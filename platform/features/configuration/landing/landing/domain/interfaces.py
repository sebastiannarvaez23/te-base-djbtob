from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import LandingSectionSchema


class ILandingSectionRepository(ABC):

    @abstractmethod
    def list_all(self) -> List[LandingSectionSchema]:
        ...

    @abstractmethod
    def get_by_key(self, key: str) -> Optional[LandingSectionSchema]:
        ...

    @abstractmethod
    def upsert(
        self, key: str, *, is_visible: bool, sort_order: int,
    ) -> LandingSectionSchema:
        ...

    @abstractmethod
    def set_visibility(self, key: str, is_visible: bool) -> Optional[LandingSectionSchema]:
        ...
