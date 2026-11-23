from __future__ import annotations

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.domain.interfaces import ICompanyOffboardingRepository
from platform.features.company.tenant.company.domain.lifecycle import PUBLIC_SCHEMA_NAME
from platform.features.company.tenant.company.domain.schemas import (
    CompanyLifecycleRecord,
    SetLegalHoldSchema,
)
from core.trace import trace_layer


class SetLegalHoldUseCase:
    def __init__(self, companies: ICompanyOffboardingRepository):
        self.companies = companies

    @trace_layer('application')
    def execute(self, data: SetLegalHoldSchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.schema_name == PUBLIC_SCHEMA_NAME:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)
        reason = (data.reason or '').strip()
        return self.companies.apply_legal_hold(
            data.company_id,
            enabled=data.enabled,
            reason=reason if data.enabled else '',
        )
