"""Bind a captured charge to the CompanySubscription period that it paid for."""
import uuid

from core.errors import AppErrorCode, AppException

from ..domain.interfaces import IChargeRepository
from ..domain.schemas import ChargeSchema
from core.trace import trace_layer


class BindChargeToPeriodUseCase:
    def __init__(self, repository: IChargeRepository):
        self._repository = repository

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> ChargeSchema:
        updated = self._repository.bind_period(charge_id, period_id)
        if updated is None:
            raise AppException(AppErrorCode.SUB_PERIOD_BIND_FAILED)
        return updated
