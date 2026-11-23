import uuid
from typing import Optional, List

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IInvoiceRepository
from ..domain.schemas import InvoiceSchema, CreateInvoiceSchema, UpdateInvoiceStatusSchema
from core.trace import trace_layer


class GetInvoicesByCompanyUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID) -> List[InvoiceSchema]:
        return self.repository.get_all_by_company(company_id)


class ListInvoicesPaginatedUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class GetInvoiceByNumberUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, invoice_number: str) -> Optional[InvoiceSchema]:
        return self.repository.get_by_invoice_number(invoice_number)


class CreateInvoiceUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateInvoiceSchema) -> InvoiceSchema:
        return self.repository.create(data)


class UpdateInvoiceStatusUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateInvoiceStatusSchema) -> Optional[InvoiceSchema]:
        return self.repository.update_status(id, data)


class DeleteInvoiceUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)
