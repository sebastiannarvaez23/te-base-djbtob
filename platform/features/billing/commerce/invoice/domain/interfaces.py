import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import InvoiceSchema, CreateInvoiceSchema, UpdateInvoiceStatusSchema


class IInvoiceRepository(ABC):

    @abstractmethod
    def get_all_by_company(self, company_id: uuid.UUID) -> List[InvoiceSchema]:
        ...

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[InvoiceSchema]:
        ...

    @abstractmethod
    def get_by_invoice_number(self, invoice_number: str) -> Optional[InvoiceSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateInvoiceSchema) -> InvoiceSchema:
        ...

    @abstractmethod
    def update_status(self, id: uuid.UUID, data: UpdateInvoiceStatusSchema) -> Optional[InvoiceSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def mark_pdf_sent(
        self,
        id: uuid.UUID,
        bucket: str,
        object_key: str,
        sent_at: datetime,
    ) -> Optional[InvoiceSchema]:
        """Persist the MinIO reference + delivery timestamp after sending the invoice PDF."""
        ...

    @abstractmethod
    def bind_period(self, invoice_id: uuid.UUID, period_id: uuid.UUID) -> int:
        """Stamp ``company_subscription_id`` on one invoice. Returns rows updated."""
        ...

    @abstractmethod
    def bind_period_for_source_charge(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> int:
        """Stamp the invoice emitted for ``charge_id``. Returns rows updated."""
        ...
