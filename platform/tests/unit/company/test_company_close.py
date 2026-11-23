"""Unit tests for company close / reopen use cases."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.application.close_company import (
    CloseCompanyUseCase,
    CompleteSelfCloseUseCase,
    ReopenCompanyUseCase,
    SelfCloseCompanyUseCase,
)
from platform.features.company.tenant.company.application.use_cases import ToggleCompanyActiveUseCase
from platform.features.company.tenant.company.domain.schemas import (
    CloseCompanySchema,
    CompleteSelfCloseSchema,
    CompanyLifecycleRecord,
    CompanyListItemSchema,
    CompanySchema,
    ReopenCompanySchema,
    SelfCloseCompanySchema,
)


pytestmark = pytest.mark.unit

COMPANY_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _record(**overrides) -> CompanyLifecycleRecord:
    payload = dict(
        id=COMPANY_ID,
        schema_name='acme_corp',
        nit='900123456',
        name='Acme Corp',
        lifecycle='ACTIVE',
        user_ids=[USER_ID],
    )
    payload.update(overrides)
    return CompanyLifecycleRecord(**payload)


def _close_schema(**overrides) -> CloseCompanySchema:
    payload = dict(
        company_id=COMPANY_ID,
        reason='Customer churn',
        actor_admin_id=ADMIN_ID,
        grace_days=90,
    )
    payload.update(overrides)
    return CloseCompanySchema(**payload)


class TestCloseCompanyUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.sessions = MagicMock()
        self.notifier = MagicMock()
        self.use_case = CloseCompanyUseCase(self.companies, self.sessions, self.notifier)

    def test_closes_active_company_revokes_sessions_and_notifies(self):
        self.companies.get_lifecycle.return_value = _record()
        closed = _record(lifecycle='CLOSED', user_ids=[USER_ID])
        self.companies.apply_close.return_value = closed

        result = self.use_case.execute(_close_schema())

        self.assertEqual(result.lifecycle, 'CLOSED')
        self.sessions.revoke_all.assert_called_once_with([USER_ID])
        self.notifier.notify_closed.assert_called_once_with(closed)
        kwargs = self.companies.apply_close.call_args.kwargs
        self.assertEqual(kwargs['reason'], 'Customer churn')
        self.assertEqual(kwargs['actor_admin_id'], ADMIN_ID)

    def test_rejects_second_close(self):
        self.companies.get_lifecycle.return_value = _record(lifecycle='CLOSED')
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(_close_schema())
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_ALREADY_CLOSED)
        self.companies.apply_close.assert_not_called()

    def test_rejects_public_schema(self):
        self.companies.get_lifecycle.return_value = _record(schema_name='public')
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(_close_schema())
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)

    def test_not_found(self):
        self.companies.get_lifecycle.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.use_case.execute(_close_schema())
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_NOT_FOUND)

    def test_session_failure_does_not_fail_close(self):
        self.companies.get_lifecycle.return_value = _record()
        self.companies.apply_close.return_value = _record(lifecycle='CLOSED')
        self.sessions.revoke_all.side_effect = RuntimeError('redis down')
        result = self.use_case.execute(_close_schema())
        self.assertEqual(result.lifecycle, 'CLOSED')

    def test_rejects_negative_grace(self):
        self.companies.get_lifecycle.return_value = _record()
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(_close_schema(grace_days=-1))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)
        self.companies.apply_close.assert_not_called()

    def test_zero_grace_exports_and_purges_immediately(self):
        now = datetime.now(dt_timezone.utc)
        store = MagicMock()
        store.put_json.return_value = 'client/tenants/acme_corp/deregistration/export.json'
        self.use_case = CloseCompanyUseCase(
            self.companies, self.sessions, self.notifier, store,
        )
        closed = _record(lifecycle='CLOSED', purge_after=now.isoformat())
        attested = _record(
            lifecycle='CLOSED',
            purge_after=now.isoformat(),
            export_attested_at=now.isoformat(),
            export_object_key='client/tenants/acme_corp/deregistration/export.json',
        )
        gone = _record(lifecycle='GONE', purge_after=now.isoformat())
        self.companies.get_lifecycle.side_effect = [
            _record(),
            closed,
            attested,
        ]
        self.companies.apply_close.return_value = closed
        self.companies.list_export_users.return_value = []
        self.companies.collect_warehouse_export.return_value = {'references': [], 'orders': []}
        self.companies.apply_export_attestation.return_value = attested
        self.companies.mark_pending_purge.return_value = _record(
            lifecycle='PENDING_PURGE', purge_after=now.isoformat(),
        )
        self.companies.apply_purge.return_value = gone

        result = self.use_case.execute(_close_schema(grace_days=0))

        self.assertEqual(result.lifecycle, 'GONE')
        kwargs = self.companies.apply_close.call_args.kwargs
        self.assertEqual(kwargs['purge_after'], kwargs['closed_at'])
        store.put_json.assert_called_once()
        store.delete_tenant_prefix.assert_called_once_with('acme_corp')
        self.companies.apply_purge.assert_called_once()
        self.sessions.revoke_all.assert_called_once()
        self.notifier.notify_closed.assert_called_once_with(closed)

    def test_zero_grace_waives_export_if_package_fails(self):
        now = datetime.now(dt_timezone.utc)
        store = MagicMock()
        store.put_json.side_effect = RuntimeError('minio down')
        self.use_case = CloseCompanyUseCase(
            self.companies, self.sessions, self.notifier, store,
        )
        closed = _record(lifecycle='CLOSED', purge_after=now.isoformat())
        attested = _record(
            lifecycle='CLOSED',
            purge_after=now.isoformat(),
            export_attested_at=now.isoformat(),
        )
        gone = _record(lifecycle='GONE', purge_after=now.isoformat())
        self.companies.get_lifecycle.side_effect = [
            _record(),
            closed,
            closed,
            attested,
        ]
        self.companies.apply_close.return_value = closed
        self.companies.apply_export_attestation.return_value = attested
        self.companies.mark_pending_purge.return_value = _record(
            lifecycle='PENDING_PURGE', purge_after=now.isoformat(),
        )
        self.companies.apply_purge.return_value = gone

        result = self.use_case.execute(_close_schema(grace_days=0))

        self.assertEqual(result.lifecycle, 'GONE')
        kwargs = self.companies.apply_export_attestation.call_args.kwargs
        self.assertEqual(kwargs['object_key'], '')
        self.companies.apply_purge.assert_called_once()


class TestSelfCloseCompanyUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.sessions = MagicMock()
        self.notifier = MagicMock()
        self.policy_gate = MagicMock()
        self.use_case = SelfCloseCompanyUseCase(
            self.companies, self.sessions, self.notifier,
            policy_gate=self.policy_gate,
        )

    def _payload(self, **overrides):
        data = dict(
            company_id=COMPANY_ID,
            confirmation='acme corp',
            actor_user_id=ADMIN_ID,
            grace_days=30,
            accepted=True,
            country='CO',
        )
        data.update(overrides)
        return SelfCloseCompanySchema(**data)

    def test_closes_when_confirmation_matches_and_spares_actor(self):
        from platform.features.company.tenant.company.domain.lifecycle import SELF_CLOSE_PENDING_REASON

        self.companies.get_lifecycle.return_value = _record()
        closed = _record(lifecycle='CLOSED', user_ids=[USER_ID, ADMIN_ID])
        self.companies.apply_close.return_value = closed
        result = self.use_case.execute(self._payload())
        self.assertEqual(result.lifecycle, 'CLOSED')
        kwargs = self.companies.apply_close.call_args.kwargs
        self.assertEqual(kwargs['spare_user_id'], ADMIN_ID)
        self.assertEqual(kwargs['reason'], SELF_CLOSE_PENDING_REASON)
        self.sessions.revoke_all.assert_called_once_with([USER_ID])
        self.companies.apply_purge.assert_not_called()
        self.policy_gate.execute.assert_called_once_with(
            actor_user_id=ADMIN_ID,
            company_id=COMPANY_ID,
            country='CO',
        )

    def test_rejects_wrong_confirmation(self):
        self.companies.get_lifecycle.return_value = _record()
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(self._payload(confirmation='otra empresa'))
        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)
        self.companies.apply_close.assert_not_called()
        self.policy_gate.execute.assert_not_called()

    def test_rejects_when_policy_not_accepted(self):
        self.companies.get_lifecycle.return_value = _record()
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(self._payload(accepted=False))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED)
        self.companies.apply_close.assert_not_called()
        self.policy_gate.execute.assert_not_called()

    def test_rejects_when_policy_unsigned(self):
        self.companies.get_lifecycle.return_value = _record()
        self.policy_gate.execute.side_effect = ValidationAppException(
            AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED,
        )
        with self.assertRaises(ValidationAppException) as ctx:
            self.use_case.execute(self._payload())
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED)
        self.companies.apply_close.assert_not_called()

    def test_zero_grace_purges_immediately_and_does_not_spare_actor(self):
        now = datetime.now(dt_timezone.utc)
        store = MagicMock()
        store.put_json.return_value = 'client/tenants/acme_corp/deregistration/export.json'
        self.use_case = SelfCloseCompanyUseCase(
            self.companies, self.sessions, self.notifier, store,
            policy_gate=self.policy_gate,
        )
        closed = _record(lifecycle='CLOSED', purge_after=now.isoformat(), user_ids=[ADMIN_ID])
        attested = _record(
            lifecycle='CLOSED',
            purge_after=now.isoformat(),
            export_attested_at=now.isoformat(),
            export_object_key='client/tenants/acme_corp/deregistration/export.json',
            user_ids=[ADMIN_ID],
        )
        gone = _record(lifecycle='GONE', purge_after=now.isoformat(), user_ids=[ADMIN_ID])
        self.companies.get_lifecycle.side_effect = [
            _record(),
            _record(),
            closed,
            attested,
        ]
        self.companies.apply_close.return_value = closed
        self.companies.list_export_users.return_value = []
        self.companies.collect_warehouse_export.return_value = {'references': [], 'orders': []}
        self.companies.apply_export_attestation.return_value = attested
        self.companies.mark_pending_purge.return_value = _record(
            lifecycle='PENDING_PURGE', purge_after=now.isoformat(),
        )
        self.companies.apply_purge.return_value = gone

        result = self.use_case.execute(self._payload(confirmation='Acme Corp', grace_days=0))

        self.assertEqual(result.lifecycle, 'GONE')
        kwargs = self.companies.apply_close.call_args.kwargs
        self.assertIsNone(kwargs['spare_user_id'])
        self.companies.apply_purge.assert_called_once()
        store.delete_tenant_prefix.assert_called_once_with('acme_corp')
        self.sessions.revoke_all.assert_called_once_with([ADMIN_ID])


class TestCompleteSelfCloseUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.sessions = MagicMock()
        self.store = MagicMock()
        self.use_case = CompleteSelfCloseUseCase(self.companies, self.sessions, self.store)

    def test_stores_reason_and_deactivates_actor(self):
        future = (datetime.now(dt_timezone.utc) + timedelta(days=10)).isoformat()
        closed = _record(lifecycle='CLOSED', purge_after=future)
        self.companies.get_lifecycle.return_value = closed
        self.companies.apply_close_reason.return_value = closed
        result = self.use_case.execute(CompleteSelfCloseSchema(
            company_id=COMPANY_ID,
            actor_user_id=ADMIN_ID,
            reason='Cost is too high',
        ))
        self.assertEqual(result.lifecycle, 'CLOSED')
        self.companies.apply_close_reason.assert_called_once_with(
            COMPANY_ID, reason='Cost is too high',
        )
        self.companies.deactivate_member.assert_called_once_with(COMPANY_ID, ADMIN_ID)
        self.sessions.revoke_all.assert_called_once_with([ADMIN_ID])
        self.companies.apply_purge.assert_not_called()

    def test_purges_immediately_when_grace_already_due(self):
        now = datetime.now(dt_timezone.utc)
        closed = _record(
            lifecycle='CLOSED',
            purge_after=now.isoformat(),
            export_attested_at=now.isoformat(),
        )
        self.companies.get_lifecycle.return_value = closed
        self.companies.apply_close_reason.return_value = closed
        self.companies.mark_pending_purge.return_value = _record(lifecycle='PENDING_PURGE')
        gone = _record(lifecycle='GONE')
        self.companies.apply_purge.return_value = gone
        self.companies.list_export_users.return_value = []
        self.companies.collect_warehouse_export.return_value = {'references': [], 'orders': []}
        self.store.put_json.return_value = 'client/tenants/acme_corp/deregistration/export.json'
        self.companies.apply_export_attestation.return_value = closed

        result = self.use_case.execute(CompleteSelfCloseSchema(
            company_id=COMPANY_ID,
            actor_user_id=ADMIN_ID,
            reason='Leaving the market',
        ))
        self.assertEqual(result.lifecycle, 'GONE')
        self.companies.apply_purge.assert_called_once()


class TestReopenCompanyUseCase(TestCase):
    def setUp(self):
        self.companies = MagicMock()
        self.use_case = ReopenCompanyUseCase(self.companies)

    def test_reopens_closed_company_inside_grace(self):
        future = (datetime.now(dt_timezone.utc) + timedelta(days=10)).isoformat()
        self.companies.get_lifecycle.return_value = _record(
            lifecycle='CLOSED',
            purge_after=future,
        )
        self.companies.apply_reopen.return_value = _record(lifecycle='ACTIVE')
        result = self.use_case.execute(ReopenCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(result.lifecycle, 'ACTIVE')
        self.companies.apply_reopen.assert_called_once_with(COMPANY_ID)

    def test_rejects_active_company(self):
        self.companies.get_lifecycle.return_value = _record(lifecycle='ACTIVE')
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(ReopenCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CANNOT_REOPEN)

    def test_rejects_legal_hold(self):
        future = (datetime.now(dt_timezone.utc) + timedelta(days=10)).isoformat()
        self.companies.get_lifecycle.return_value = _record(
            lifecycle='CLOSED',
            legal_hold=True,
            purge_after=future,
        )
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(ReopenCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_LEGAL_HOLD)

    def test_rejects_expired_grace(self):
        past = (datetime.now(dt_timezone.utc) - timedelta(days=1)).isoformat()
        self.companies.get_lifecycle.return_value = _record(
            lifecycle='CLOSED',
            purge_after=past,
        )
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(ReopenCompanySchema(company_id=COMPANY_ID))
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_GRACE_EXPIRED)
        self.companies.apply_reopen.assert_not_called()


class TestToggleCompanyActiveUseCase(TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.use_case = ToggleCompanyActiveUseCase(self.repo)

    def test_toggles_when_company_is_active(self):
        self.repo.get_by_id.return_value = CompanySchema(
            id=COMPANY_ID,
            schema_name='acme_corp',
            nit='900123456',
            name='Acme',
            address='Street 1',
            geo_city_id=uuid.uuid4(),
            lifecycle='ACTIVE',
        )
        toggled = MagicMock(spec=CompanyListItemSchema)
        self.repo.toggle_active.return_value = toggled
        result = self.use_case.execute(COMPANY_ID)
        self.assertIs(result, toggled)
        self.repo.toggle_active.assert_called_once_with(COMPANY_ID)

    def test_refuses_toggle_on_closed_company(self):
        self.repo.get_by_id.return_value = CompanySchema(
            id=COMPANY_ID,
            schema_name='acme_corp',
            nit='900123456',
            name='Acme',
            address='Street 1',
            geo_city_id=uuid.uuid4(),
            lifecycle='CLOSED',
        )
        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(COMPANY_ID)
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_ALREADY_CLOSED)
        self.repo.toggle_active.assert_not_called()


def test_close_body_requires_reason():
    from platform.features.company.tenant.company.presentation.bodies import CloseCompanyBody

    data, error = CloseCompanyBody({}).parse()
    assert data is None
    assert any(item['field'] == 'reason' for item in error.data['errors'])


def test_company_schema_defaults_lifecycle_active():
    schema = CompanySchema(
        schema_name='acme',
        nit='900123456',
        name='Acme',
        address='Street 1',
        geo_city_id=uuid.uuid4(),
    )
    assert schema.lifecycle == 'ACTIVE'
    assert schema.legal_hold is False


def test_close_schema_defaults_grace_from_platform_parameter():
    from platform.features.company.tenant.company.domain.lifecycle import (
        CLOSE_GRACE_PARAM,
        DEFAULT_CLOSE_GRACE_DAYS,
    )
    from platform.features.company.tenant.company.domain.schemas import CloseCompanySchema

    assert CLOSE_GRACE_PARAM == 'DAYS_COMP_DEREGISTRA'
    schema = CloseCompanySchema(company_id=COMPANY_ID, reason='Customer churn')
    assert schema.grace_days == DEFAULT_CLOSE_GRACE_DAYS
    assert schema.grace_days == 30
