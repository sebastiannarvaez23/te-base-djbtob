from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import HandbookNodeSchema


class ICatalogRepository(ABC):
    """Árbol de espacios/secciones. Persistencia en el siguiente corte."""

    @abstractmethod
    def list_nodes(self, *, locale: str) -> List[HandbookNodeSchema]:
        ...

    @abstractmethod
    def get_by_slug(self, slug: str, *, locale: str) -> Optional[HandbookNodeSchema]:
        ...
