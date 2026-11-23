from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from .schemas import HandbookChunkSchema, HandbookRetrieveHitSchema


class IIngestRepository(ABC):
    """Chunks del corpus (pgvector más adelante). Persistencia en el siguiente corte."""

    @abstractmethod
    def replace_chunks(self, page_id: UUID, chunks: List[HandbookChunkSchema]) -> int:
        ...

    @abstractmethod
    def search(self, query: str, *, limit: int = 8) -> List[HandbookRetrieveHitSchema]:
        ...
