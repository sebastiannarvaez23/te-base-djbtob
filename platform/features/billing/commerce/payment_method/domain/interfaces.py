import uuid
from abc import ABC, abstractmethod
from typing import Optional, List

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import PaymentMethodSchema, CreatePaymentMethodSchema, UpdatePaymentMethodSchema


class IPaymentMethodRepository(ABC):

    @abstractmethod
    def get_all(self) -> List[PaymentMethodSchema]:
        ...

    @abstractmethod
    def get_all_by_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[PaymentMethodSchema]:
        ...

    @abstractmethod
    def create(self, data: CreatePaymentMethodSchema) -> PaymentMethodSchema:
        ...

    @abstractmethod
    def partial_update(self, id: uuid.UUID, data: UpdatePaymentMethodSchema) -> Optional[PaymentMethodSchema]:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: CreatePaymentMethodSchema) -> Optional[PaymentMethodSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
