import uuid
from typing import Optional, List

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IPaymentMethodRepository
from ..domain.schemas import PaymentMethodSchema, CreatePaymentMethodSchema, UpdatePaymentMethodSchema
from core.trace import trace_layer


class GetAllPaymentMethodsUseCase:
    def __init__(self, repository: IPaymentMethodRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> List[PaymentMethodSchema]:
        return self.repository.get_all()


class GetPaymentMethodsByCompanyUseCase:
    def __init__(self, repository: IPaymentMethodRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_all_by_company(company_id, query)


class CreatePaymentMethodUseCase:
    def __init__(self, repository: IPaymentMethodRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreatePaymentMethodSchema) -> PaymentMethodSchema:
        return self.repository.create(data)


class UpdatePaymentMethodUseCase:
    def __init__(self, repository: IPaymentMethodRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdatePaymentMethodSchema) -> Optional[PaymentMethodSchema]:
        return self.repository.partial_update(id, data)


class DeletePaymentMethodUseCase:
    def __init__(self, repository: IPaymentMethodRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)
