"""Unit tests for PurgeUnverifiedTenantsUseCase.

What the sweep MUST do:

  * Only target Companies whose Users **all** have ``email_verified_at IS NULL``
    AND whose ``created`` is before the cutoff.
  * Never touch Companies with at least one verified user.
  * Never touch Companies with zero users (defends against nuking system
    rows or migration artifacts).
  * Never touch the public tenant row (defence in depth — public has no
    Users in this codebase, but the explicit exclusion guards future
    drift).
  * Delete Users first (FK is PROTECT) before calling Company.delete.
  * Drop the schema by passing ``force_drop=True`` to Company.delete.
  * Per-tenant failures must not abort the sweep — log and continue.

We mock the User and Company querysets directly because the sweep
exercises queryset annotations + cross-app deletion which would require
a full Django test DB. The behavioural surface (the order and arguments
of repository calls) is what we verify here.
"""
from datetime import timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.utils import timezone

from client.features.security.lifecycle.onboarding.application.use_cases.purge_unverified_tenants import (
    PurgeUnverifiedTenantsUseCase,
    UnverifiedTenantsPurgeResult,
)


COMPANY_PATH = 'platform.features.company.tenant.company.models.Company'
USER_PATH = 'client.features.security.lifecycle.registration.models.User'
TRANSACTION_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.purge_unverified_tenants.transaction'
)
USE_CASE_MOD = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.purge_unverified_tenants'
)


class _NoopAtomic:
    """Stand-in for ``django.db.transaction.atomic()`` that never touches
    a real connection. Required because the use case wraps each per-tenant
    delete in ``with transaction.atomic()`` and unit tests run without DB."""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False  # don't swallow exceptions


def _company(schema_name='acme', raise_on_delete=False):
    """Construct a Company-like mock that records its delete() args."""
    c = MagicMock()
    c.id = 'cmp-' + schema_name
    c.schema_name = schema_name
    if raise_on_delete:
        c.delete.side_effect = RuntimeError('boom')
    return c


class _FakeQuerySet:
    """Minimal queryset stand-in: supports both ``count()`` and iteration.

    The use case calls .count() in dry_run mode and ``list(qs)`` in the
    real run; MagicMock's auto-spec'd __iter__ doesn't interact cleanly
    with list(), so a tiny concrete class is the path of least friction.
    """
    def __init__(self, items, count=None):
        self._items = list(items)
        self._count = len(self._items) if count is None else count

    def __iter__(self):
        return iter(self._items)

    def count(self):
        return self._count


class TestPurgeUnverifiedTenantsHappyPath(TestCase):

    def test_dry_run_counts_without_deleting(self):
        candidates = [_company('a'), _company('b'), _company('c')]

        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User:
            qs = _FakeQuerySet(candidates)
            Company.objects.annotate.return_value.filter.return_value.exclude.return_value = qs

            users_qs = MagicMock()
            users_qs.count.return_value = 7
            User.objects.filter.return_value = users_qs

            result = PurgeUnverifiedTenantsUseCase(retention_days=7).execute(dry_run=True)

        self.assertEqual(result, UnverifiedTenantsPurgeResult(
            tenants_deleted=3, users_deleted=7,
        ))
        # Strict: dry-run must not call .delete() on anything.
        for c in candidates:
            c.delete.assert_not_called()

    def test_each_candidate_has_users_deleted_then_company_with_force_drop(self):
        a, b = _company('a'), _company('b')

        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User, \
                patch(TRANSACTION_PATH) as txn, \
                patch(f'{USE_CASE_MOD}._has_settled_billing', return_value=False), \
                patch(f'{USE_CASE_MOD}._clear_public_billing') as clear_billing:
            txn.atomic.return_value = _NoopAtomic()
            qs = _FakeQuerySet([a, b])
            Company.objects.annotate.return_value.filter.return_value.exclude.return_value = qs

            users_qs = MagicMock()
            users_qs.delete.return_value = (1, {})
            User.objects.filter.return_value = users_qs

            result = PurgeUnverifiedTenantsUseCase(retention_days=7).execute()

        self.assertEqual(result.tenants_deleted, 2)
        self.assertEqual(result.users_deleted, 2)  # 1 per company
        self.assertEqual(clear_billing.call_count, 2)
        # force_drop=True is the whole point — without it, the schema
        # leaks even though the row is gone.
        a.delete.assert_called_once_with(force_drop=True)
        b.delete.assert_called_once_with(force_drop=True)

    def test_skips_tenant_with_settled_billing(self):
        paid = _company('paid')
        free = _company('free')

        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User, \
                patch(TRANSACTION_PATH) as txn, \
                patch(f'{USE_CASE_MOD}._has_settled_billing', side_effect=[True, False]), \
                patch(f'{USE_CASE_MOD}._clear_public_billing') as clear_billing:
            txn.atomic.return_value = _NoopAtomic()
            qs = _FakeQuerySet([paid, free])
            Company.objects.annotate.return_value.filter.return_value.exclude.return_value = qs

            users_qs = MagicMock()
            users_qs.delete.return_value = (1, {})
            User.objects.filter.return_value = users_qs

            result = PurgeUnverifiedTenantsUseCase(retention_days=7).execute()

        self.assertEqual(result.tenants_deleted, 1)
        paid.delete.assert_not_called()
        free.delete.assert_called_once_with(force_drop=True)
        clear_billing.assert_called_once_with(free)

    def test_per_tenant_failure_does_not_abort_sweep(self):
        """The sweep is best-effort: a single tenant whose delete blows
        up (e.g. a row was verified between query and delete) must not
        prevent the remaining candidates from being processed."""
        bad = _company('bad', raise_on_delete=True)
        good = _company('good')

        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User, \
                patch(TRANSACTION_PATH) as txn, \
                patch(f'{USE_CASE_MOD}._has_settled_billing', return_value=False), \
                patch(f'{USE_CASE_MOD}._clear_public_billing'):
            txn.atomic.return_value = _NoopAtomic()
            qs = _FakeQuerySet([bad, good])
            Company.objects.annotate.return_value.filter.return_value.exclude.return_value = qs

            users_qs = MagicMock()
            users_qs.delete.return_value = (1, {})
            User.objects.filter.return_value = users_qs

            result = PurgeUnverifiedTenantsUseCase(retention_days=7).execute()

        # One success, one failure — the surviving counter reflects
        # only the tenant we actually deleted.
        self.assertEqual(result.tenants_deleted, 1)
        good.delete.assert_called_once_with(force_drop=True)


class TestPurgeUnverifiedTenantsCutoff(TestCase):
    """The cutoff is built from ``timezone.now().date() - retention_days``.

    Verifying this catches off-by-one regressions (e.g. switching to a
    timestamp comparison that rejects rows modified the same day).
    """

    def test_filter_uses_created_lte_cutoff(self):
        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User:
            qs = _FakeQuerySet([])
            Company.objects.annotate.return_value.filter.return_value.exclude.return_value = qs
            User.objects.filter.return_value = MagicMock(count=lambda: 0)

            PurgeUnverifiedTenantsUseCase(retention_days=14).execute(dry_run=True)

        filter_call = Company.objects.annotate.return_value.filter.call_args
        kwargs = filter_call.kwargs
        self.assertEqual(kwargs['total_users__gt'], 0)
        self.assertEqual(kwargs['verified_users'], 0)
        # Allow either same day or earlier:
        cutoff = kwargs['created__lte']
        expected = timezone.now().date() - timedelta(days=14)
        self.assertEqual(cutoff, expected)

    def test_excludes_public_schema(self):
        """Defence in depth: even if some other code accidentally adds a
        Company row with schema_name='public', we never try to drop the
        public schema."""
        with patch(COMPANY_PATH) as Company, patch(USER_PATH) as User:
            qs = _FakeQuerySet([])
            filtered = Company.objects.annotate.return_value.filter.return_value
            filtered.exclude.return_value = qs
            User.objects.filter.return_value = MagicMock(count=lambda: 0)

            PurgeUnverifiedTenantsUseCase().execute(dry_run=True)

        filtered.exclude.assert_called_once_with(schema_name='public')


class TestUnverifiedTenantsPurgeResultIsFrozen(TestCase):

    def test_dataclass_is_frozen(self):
        """The result is the audit trail — callers should not be able to
        retroactively edit the counts."""
        result = UnverifiedTenantsPurgeResult(tenants_deleted=1, users_deleted=2)
        with self.assertRaises(Exception):  # FrozenInstanceError
            result.tenants_deleted = 999  # type: ignore[misc]
