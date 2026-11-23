from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.domain.interfaces import (
    ICompanyOffboardingRepository,
    ITenantExportStore,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    LIFECYCLE_GONE,
    PUBLIC_SCHEMA_NAME,
    PURGEABLE_LIFECYCLES,
)
from platform.features.company.tenant.company.domain.schemas import (
    CompanyLifecycleRecord,
    PurgeClosedCompanySchema,
)
from core.trace import trace_layer


logger = logging.getLogger('app.company')


def _parse_instant(value: str):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def assert_purge_allowed(record: CompanyLifecycleRecord, *, now, force: bool) -> None:
    if record.schema_name == PUBLIC_SCHEMA_NAME:
        raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)
    if record.lifecycle not in PURGEABLE_LIFECYCLES:
        raise ConflictException(AppErrorCode.COMPANY_PURGE_BLOCKED)
    if record.legal_hold:
        raise ConflictException(AppErrorCode.COMPANY_LEGAL_HOLD)
    if not record.export_attested_at:
        raise ConflictException(AppErrorCode.COMPANY_PURGE_BLOCKED)
    if force:
        return
    if not record.purge_after or now < _parse_instant(record.purge_after):
        raise ConflictException(AppErrorCode.COMPANY_PURGE_BLOCKED)


class PurgeClosedCompanyUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        store: ITenantExportStore,
    ):
        self.companies = companies
        self.store = store

    @trace_layer('application')
    def execute(self, data: PurgeClosedCompanySchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.lifecycle == LIFECYCLE_GONE:
            return record
        now = timezone.now()
        assert_purge_allowed(record, now=now, force=data.force)
        if data.dry_run:
            return record
        pending = self.companies.mark_pending_purge(data.company_id)
        try:
            self.store.delete_tenant_prefix(pending.schema_name)
        except Exception:
            logger.warning(
                'Tenant storage prefix delete failed company_id=%s schema=%s',
                data.company_id,
                pending.schema_name,
                exc_info=True,
            )
        return self.companies.apply_purge(data.company_id, now=now, dry_run=False)


class PurgeDueClosedCompaniesUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        store: ITenantExportStore,
    ):
        self.companies = companies
        self.store = store

    @trace_layer('application')
    def execute(self, *, dry_run: bool = False) -> dict:
        now = timezone.now()
        purged = 0
        skipped = 0
        for record in self.companies.list_purge_candidates(now=now):
            try:
                PurgeClosedCompanyUseCase(self.companies, self.store).execute(
                    PurgeClosedCompanySchema(
                        company_id=record.id,
                        dry_run=dry_run,
                    ),
                )
                purged += 1
            except Exception:
                logger.warning(
                    'Purge candidate skipped company_id=%s',
                    record.id,
                    exc_info=True,
                )
                skipped += 1
        return {'purged': purged, 'skipped': skipped, 'dry_run': dry_run}
