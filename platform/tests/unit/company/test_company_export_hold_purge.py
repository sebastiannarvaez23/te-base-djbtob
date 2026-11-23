"""Unit tests for export, legal hold and purge use cases."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.application.export_company import (
    ExportClosedTenantUseCase,
)
from platform.features.company.tenant.company.application.legal_hold import SetLegalHoldUseCase
from platform.features.company.tenant.company.application.purge_company import (
    PurgeClosedCompanyUseCase,
    PurgeDueClosedCompaniesUseCase,
)
from platform.features.company.tenant.company.domain.schemas import (
    CompanyLifecycleRecord,
    ExportClosedTenantSchema,
    PurgeClosedCompanySchema,
    SetLegalHoldSchema,
)


pytestmark = pytest.mark.unit

COMPANY_ID = uuid.uuid4()


def _record(**overrides) -> CompanyLifecycleRecord:
    future = (datetime.now(dt_timezone.utc) + timedelta(days=10)).isoformat()
    payload = dict(
        id=COMPANY_ID,
        schema_name='acme_corp',
        nit='9001234567',
        name='Acme Corp',
        lifecycle='CLOSED',
        purge_after=future,
        export_attested_at=datetime.now(dt_timezone.utc).isoformat(),
    )
    payload.update(overrides)
    return CompanyLifecycleRecord(**payload)


class TestSetLegalHoldUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.use_case = SetLegalHoldUseCase(self.companies)

    def test_enables_hold(self):
        self.companies.get_lifecycle.return_value = _record()
        held = _record(legal_hold=True, legal_hold_reason='Open dispute')
        self.companies.apply_legal_hold.return_value = held
        result = self.use_case.execute(SetLegalHoldSchema(
            company_id=COMPANY_ID,
            enabled=True,
            reason='Open dispute',
        ))
        self.assertTrue(result.legal_hold)
        self.companies.apply_legal_hold.assert_called_once_with(
            COMPANY_ID, enabled=True, reason='Open dispute',
        )

    def test_rejects_public_schema(self):
        self.companies.get_lifecycle.return_value = _record(schema_name='public')
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(SetLegalHoldSchema(
                company_id=COMPANY_ID, enabled=True, reason='Hold',
            ))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)


class TestExportClosedTenantUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.store = MagicMock()
        self.use_case = ExportClosedTenantUseCase(self.companies, self.store)

    def test_uploads_package_and_attests(self):
        self.companies.get_lifecycle.return_value = _record(export_attested_at=None)
        self.companies.list_export_users.return_value = [{'email': 'a@acme.com'}]
        self.companies.collect_warehouse_export.return_value = {'references': [], 'orders': []}
        self.store.put_json.return_value = 'client/tenants/acme_corp/deregistration/export.json'
        attested = _record(export_object_key='client/tenants/acme_corp/deregistration/export.json')
        self.companies.apply_export_attestation.return_value = attested

        result = self.use_case.execute(ExportClosedTenantSchema(company_id=COMPANY_ID))
        self.assertEqual(result.export_object_key, 'client/tenants/acme_corp/deregistration/export.json')
        self.store.put_json.assert_called_once()
        self.assertEqual(self.store.put_json.call_args.args[0], 'acme_corp')
        kwargs = self.companies.apply_export_attestation.call_args.kwargs
        self.assertEqual(kwargs['object_key'], 'client/tenants/acme_corp/deregistration/export.json')

    def test_waiver_skips_upload(self):
        self.companies.get_lifecycle.return_value = _record(export_attested_at=None)
        self.companies.apply_export_attestation.return_value = _record()
        self.use_case.execute(ExportClosedTenantSchema(
            company_id=COMPANY_ID, waived=True, reason='Client declined the package',
        ))
        self.store.put_json.assert_not_called()
        kwargs = self.companies.apply_export_attestation.call_args.kwargs
        self.assertEqual(kwargs['object_key'], '')

    def test_rejects_active_company(self):
        self.companies.get_lifecycle.return_value = _record(lifecycle='ACTIVE')
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(ExportClosedTenantSchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_PURGE_BLOCKED)

    def test_allows_pending_purge_reexport(self):
        self.companies.get_lifecycle.return_value = _record(
            lifecycle='PENDING_PURGE', export_attested_at=None,
        )
        self.companies.list_export_users.return_value = []
        self.companies.collect_warehouse_export.return_value = {'references': [], 'orders': []}
        self.store.put_json.return_value = 'client/tenants/acme_corp/deregistration/export.json'
        self.companies.apply_export_attestation.return_value = _record(
            lifecycle='PENDING_PURGE',
            export_object_key='client/tenants/acme_corp/deregistration/export.json',
        )
        result = self.use_case.execute(ExportClosedTenantSchema(company_id=COMPANY_ID))
        self.assertEqual(result.export_object_key, 'client/tenants/acme_corp/deregistration/export.json')


class TestPurgeClosedCompanyUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.store = MagicMock()
        self.use_case = PurgeClosedCompanyUseCase(self.companies, self.store)

    def test_purges_due_closed_company(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        closed = _record(purge_after=past)
        self.companies.get_lifecycle.return_value = closed
        self.companies.mark_pending_purge.return_value = _record(
            lifecycle='PENDING_PURGE', purge_after=past,
        )
        gone = _record(lifecycle='GONE', purge_after=past)
        self.companies.apply_purge.return_value = gone

        result = self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(result.lifecycle, 'GONE')
        self.store.delete_tenant_prefix.assert_called_once_with('acme_corp')
        self.companies.apply_purge.assert_called_once()

    def test_retries_pending_purge(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        pending = _record(lifecycle='PENDING_PURGE', purge_after=past)
        self.companies.get_lifecycle.return_value = pending
        self.companies.mark_pending_purge.return_value = pending
        self.companies.apply_purge.return_value = _record(lifecycle='GONE', purge_after=past)
        result = self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(result.lifecycle, 'GONE')
        self.companies.apply_purge.assert_called_once()

    def test_dry_run_does_not_mutate(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        self.companies.get_lifecycle.return_value = _record(purge_after=past)
        result = self.use_case.execute(
            PurgeClosedCompanySchema(company_id=COMPANY_ID, dry_run=True),
        )
        self.assertEqual(result.lifecycle, 'CLOSED')
        self.companies.mark_pending_purge.assert_not_called()
        self.companies.apply_purge.assert_not_called()
        self.store.delete_tenant_prefix.assert_not_called()

    def test_blocks_without_export(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        self.companies.get_lifecycle.return_value = _record(
            purge_after=past, export_attested_at=None,
        )
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_PURGE_BLOCKED)

    def test_blocks_legal_hold(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        self.companies.get_lifecycle.return_value = _record(
            purge_after=past, legal_hold=True,
        )
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_LEGAL_HOLD)

    def test_already_gone_is_idempotent(self):
        self.companies.get_lifecycle.return_value = _record(lifecycle='GONE')
        result = self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(result.lifecycle, 'GONE')
        self.companies.apply_purge.assert_not_called()

    def test_not_found(self):
        self.companies.get_lifecycle.return_value = None
        with self.assertRaises(NotFoundException):
            self.use_case.execute(PurgeClosedCompanySchema(company_id=COMPANY_ID))


class TestPurgeDueClosedCompaniesUseCase(TestCase):
    def test_iterates_candidates(self):
        companies = MagicMock()
        store = MagicMock()
        due = _record(purge_after=(datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat())
        companies.list_purge_candidates.return_value = [due]
        companies.get_lifecycle.return_value = due
        companies.mark_pending_purge.return_value = due
        companies.apply_purge.return_value = _record(lifecycle='GONE')
        result = PurgeDueClosedCompaniesUseCase(companies, store).execute()
        self.assertEqual(result['purged'], 1)
        self.assertEqual(result['skipped'], 0)
