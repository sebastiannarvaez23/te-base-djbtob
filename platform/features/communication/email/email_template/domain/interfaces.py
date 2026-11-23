import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from core.email.domain.interfaces import IEmailService  # noqa: F401 — re-export histórico

from .schemas import CreateEmailTemplateSchema, EmailTemplateSchema, UpdateEmailTemplateSchema

__all__ = ['IEmailService', 'IEmailTemplateRepository']


class IEmailTemplateRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[EmailTemplateSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[EmailTemplateSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[EmailTemplateSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateEmailTemplateSchema) -> EmailTemplateSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateEmailTemplateSchema) -> Optional[EmailTemplateSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
