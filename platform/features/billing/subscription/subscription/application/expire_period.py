"""Expire periods whose vigencia passed with auto_renew off and no pending change."""

from uuid import UUID

from ..domain.interfaces import ICompanyPeriodRepository
from core.trace import trace_layer


class ExpirePeriodUseCase:
    def __init__(self, repository: ICompanyPeriodRepository):
        self._repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID | None = None) -> int:
        return self._repository.expire_due(company_id)
