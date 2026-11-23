from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone
from uuid import UUID

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.domain.interfaces import (
    ICompanyOffboardingRepository,
    ITenantExportStore,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    LIFECYCLE_CLOSED,
    LIFECYCLE_PENDING_PURGE,
    PUBLIC_SCHEMA_NAME,
)
from platform.features.company.tenant.company.domain.schemas import (
    CompanyLifecycleRecord,
    ExportClosedTenantSchema,
    TenantExportDownloadSchema,
)
from core.trace import trace_layer


class ExportClosedTenantUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        store: ITenantExportStore,
    ):
        self.companies = companies
        self.store = store

    @trace_layer('application')
    def execute(self, data: ExportClosedTenantSchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.schema_name == PUBLIC_SCHEMA_NAME:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)
        if record.lifecycle not in (LIFECYCLE_CLOSED, LIFECYCLE_PENDING_PURGE):
            raise ConflictException(AppErrorCode.COMPANY_PURGE_BLOCKED)
        if data.waived and len((data.reason or '').strip()) < 3:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)

        now = datetime.now(dt_timezone.utc)
        object_key = record.export_object_key or ''
        if not data.waived:
            payload = {
                'exported_at': now.isoformat(),
                'company': {
                    'id': str(record.id),
                    'name': record.name,
                    'nit': record.nit,
                    'schema_name': record.schema_name,
                },
                'users': self.companies.list_export_users(record.id),
                'waiver': False,
            }
            object_key = self.store.put_json(
                record.schema_name,
                json.dumps(payload, default=str).encode('utf-8'),
            )
        return self.companies.apply_export_attestation(
            data.company_id,
            actor_admin_id=data.actor_admin_id,
            attested_at=now,
            object_key=object_key,
        )


class GetTenantExportDownloadUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        store: ITenantExportStore,
    ):
        self.companies = companies
        self.store = store

    @trace_layer('application')
    def execute(self, company_id: UUID) -> TenantExportDownloadSchema:
        record = self.companies.get_lifecycle(company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if not record.export_object_key:
            raise ConflictException(AppErrorCode.COMPANY_PURGE_BLOCKED)
        return TenantExportDownloadSchema(
            company_id=record.id,
            object_key=record.export_object_key,
            download_url=self.store.presign(record.export_object_key),
            attested_at=record.export_attested_at,
        )
