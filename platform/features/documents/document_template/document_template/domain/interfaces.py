import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import (
    CreateDocumentTemplateSchema,
    DocumentTemplateListItemSchema,
    DocumentTemplateSchema,
    UpdateDocumentTemplateSchema,
)


class IDocumentTemplateRepository(ABC):

    @abstractmethod
    def get_all(
        self,
        filters: dict | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[List[DocumentTemplateListItemSchema], int]:
        """Return (page_items, total_count). ``limit=None`` returns the full set."""
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[DocumentTemplateSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[DocumentTemplateSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateDocumentTemplateSchema) -> DocumentTemplateSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateDocumentTemplateSchema) -> Optional[DocumentTemplateSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
