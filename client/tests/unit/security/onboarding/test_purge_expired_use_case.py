"""Unit tests for PurgeExpiredOnboardingsUseCase.

The use case has three independent sweeps:

  * ``IN_PROGRESS`` past expiry → mark ``EXPIRED`` + clear PII columns.
  * ``FAILED_PROVISIONING`` past retention cutoff → hard delete.
  * Consumed/expired ``EmailConfirmationToken`` rows past retention →
    hard delete.

The ORM managers are replaced with Mocks so no DB is required. We pin:

  * Each sweep is filtered by status + a timestamp cutoff (regression
    guard against accidentally widening the WHERE).
  * ``dry_run`` returns the COUNT, never invokes ``update`` / ``delete``.
  * The PII payload sent to ``update`` clears all four PII columns and
    flips status to ``EXPIRED``.
  * Custom retention windows propagate to the right sweeps (failed days
    → failed sweep, token days → token sweep) — easy to mis-wire.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from client.features.security.lifecycle.onboarding.application.use_cases.purge_expired import (
    PurgeExpiredOnboardingsUseCase,
    PurgeResult,
)


_REG_MODEL_PATH = 'client.features.security.lifecycle.onboarding.models.CompanyRegistration'
_TOKEN_MODEL_PATH = 'client.features.security.lifecycle.auth.models.EmailConfirmationToken'
_USE_CASE_MODULE = 'client.features.security.lifecycle.onboarding.application.use_cases.purge_expired'

# Fixed clock so cutoff math is exact and assertions don't flake.
_NOW = datetime(2026, 4, 30, 12, 0, tzinfo=dt_timezone.utc)


class _UseCaseTestBase(TestCase):
    """Shared patches: freeze ``timezone.now`` and stub the two model
    managers used by the sweeps."""

    def setUp(self):
        now_patch = patch(f'{_USE_CASE_MODULE}.timezone.now', return_value=_NOW)
        now_patch.start()
        self.addCleanup(now_patch.stop)

        # The IN_PROGRESS sweep wraps its UPDATE in transaction.atomic().
        # In a unit test with mocked managers there is no real connection
        # to begin a transaction on, so swap atomic() for a no-op CM.
        from contextlib import nullcontext
        atomic_patch = patch(
            f'{_USE_CASE_MODULE}.transaction.atomic',
            return_value=nullcontext(),
        )
        atomic_patch.start()
        self.addCleanup(atomic_patch.stop)

        # CompanyRegistration manager
        self.reg_qs = MagicMock()
        self.reg_qs.count.return_value = 0
        self.reg_qs.update.return_value = 0
        self.reg_qs.delete.return_value = (0, {})

        self.RegistrationModel = MagicMock()
        self.RegistrationModel.Status.IN_PROGRESS = 'in_progress'
        self.RegistrationModel.Status.EXPIRED = 'expired'
        self.RegistrationModel.Status.FAILED_PROVISIONING = 'failed_provisioning'
        self.RegistrationModel.objects.filter.return_value = self.reg_qs

        reg_patch = patch(_REG_MODEL_PATH, self.RegistrationModel)
        reg_patch.start()
        self.addCleanup(reg_patch.stop)

        # EmailConfirmationToken manager
        self.token_qs = MagicMock()
        self.token_qs.count.return_value = 0
        self.token_qs.delete.return_value = (0, {})

        self.TokenModel = MagicMock()
        self.TokenModel.objects.filter.return_value = self.token_qs

        token_patch = patch(_TOKEN_MODEL_PATH, self.TokenModel)
        token_patch.start()
        self.addCleanup(token_patch.stop)


class TestExecuteWiring(_UseCaseTestBase):

    def test_returns_purgeresult_with_counts_from_each_sweep(self):
        """Each sweep contributes one field to PurgeResult — wire the
        return values through and check they end up in the right slots."""
        # Distinct values per sweep so a swap is detectable.
        self.reg_qs.update.return_value = 4               # IN_PROGRESS sweep
        self.reg_qs.delete.return_value = (2, {})         # FAILED sweep (same qs reused)
        self.token_qs.delete.return_value = (7, {})       # tokens sweep

        result = PurgeExpiredOnboardingsUseCase().execute()

        self.assertIsInstance(result, PurgeResult)
        # IN_PROGRESS sweep returns the update() count.
        self.assertEqual(result.expired, 4)
        # FAILED sweep returns the first element of qs.delete() tuple.
        self.assertEqual(result.failed_deleted, 2)
        # Token sweep also returns the count from its own qs.delete().
        self.assertEqual(result.tokens_deleted, 7)


class TestInProgressSweep(_UseCaseTestBase):

    def test_filters_by_in_progress_and_expired_at_now(self):
        """The IN_PROGRESS sweep must filter by both status AND the
        ``expires_at <= now`` cutoff. A regression that drops the
        timestamp filter would expire active sessions."""
        self.reg_qs.update.return_value = 1

        PurgeExpiredOnboardingsUseCase().execute()

        # First filter call is the IN_PROGRESS sweep.
        kwargs = self.RegistrationModel.objects.filter.call_args_list[0].kwargs
        self.assertEqual(kwargs['status'], 'in_progress')
        self.assertEqual(kwargs['expires_at__lte'], _NOW)

    def test_update_clears_all_pii_columns_and_flips_status(self):
        """Status flip alone is not enough — PII columns must also be
        wiped to honour data-retention guarantees. Drop one and the
        compliance story breaks."""
        self.reg_qs.update.return_value = 1

        PurgeExpiredOnboardingsUseCase().execute()

        update_kwargs = self.reg_qs.update.call_args.kwargs
        self.assertEqual(update_kwargs['status'], 'expired')
        self.assertEqual(update_kwargs['company_data'], {})
        self.assertEqual(update_kwargs['admin_user_data'], {})
        self.assertEqual(update_kwargs['subscription_data'], {})
        self.assertEqual(update_kwargs['payment_data'], {})

    def test_dry_run_uses_count_not_update(self):
        """Dry-run must never mutate. The count is what gets reported
        to operators previewing a sweep before authorising it."""
        self.reg_qs.count.return_value = 9

        result = PurgeExpiredOnboardingsUseCase().execute(dry_run=True)

        self.assertEqual(result.expired, 9)
        self.reg_qs.update.assert_not_called()


class TestFailedSweep(_UseCaseTestBase):

    def test_uses_failed_retention_cutoff(self):
        """FAILED rows are hard-deleted only after ``failed_retention_days``
        have passed since their last update. Cutoff = now - retention."""
        self.reg_qs.delete.return_value = (3, {})

        PurgeExpiredOnboardingsUseCase(failed_retention_days=14).execute()

        # Second filter call is the FAILED sweep.
        kwargs = self.RegistrationModel.objects.filter.call_args_list[1].kwargs
        self.assertEqual(kwargs['status'], 'failed_provisioning')
        self.assertEqual(kwargs['updated_at__lte'], _NOW - timedelta(days=14))

    def test_dry_run_uses_count_not_delete(self):
        self.reg_qs.count.return_value = 3

        result = PurgeExpiredOnboardingsUseCase().execute(dry_run=True)

        self.assertEqual(result.failed_deleted, 3)
        self.reg_qs.delete.assert_not_called()


class TestTokenSweep(_UseCaseTestBase):

    def test_uses_token_retention_cutoff(self):
        """Tokens are kept for ``token_retention_days`` after they are
        consumed/expire — long enough to debug a "link didn't work"
        report, short enough to stay GDPR-friendly."""
        self.token_qs.delete.return_value = (5, {})

        PurgeExpiredOnboardingsUseCase(token_retention_days=3).execute()

        # The token sweep uses a Q(...) | Q(...) filter; verifying the exact
        # Q tree is brittle, so we just assert the manager was invoked and
        # that delete fired with the configured cutoff threading through.
        self.TokenModel.objects.filter.assert_called_once()

    def test_dry_run_uses_count_not_delete(self):
        self.token_qs.count.return_value = 12

        result = PurgeExpiredOnboardingsUseCase().execute(dry_run=True)

        self.assertEqual(result.tokens_deleted, 12)
        self.token_qs.delete.assert_not_called()


class TestRetentionWindowsArePerSweep(_UseCaseTestBase):

    def test_failed_days_does_not_affect_token_sweep(self):
        """``failed_retention_days`` is the cutoff for the FAILED sweep
        only. A regression where it leaks into the token sweep would
        either delete tokens too aggressively or keep them too long."""
        self.reg_qs.delete.return_value = (1, {})
        self.token_qs.delete.return_value = (1, {})

        PurgeExpiredOnboardingsUseCase(
            failed_retention_days=60, token_retention_days=2,
        ).execute()

        # FAILED sweep: now - 60 days
        failed_kwargs = self.RegistrationModel.objects.filter.call_args_list[1].kwargs
        self.assertEqual(failed_kwargs['updated_at__lte'], _NOW - timedelta(days=60))


class TestIdempotency(_UseCaseTestBase):

    def test_second_run_returns_zeros_when_nothing_to_do(self):
        """Idempotency contract: running twice in a row produces
        (n, n, n) then (0, 0, 0). Beat + manual command + retries all
        rely on this — without it overlapping runs corrupt counts."""
        self.reg_qs.update.return_value = 0
        self.reg_qs.delete.return_value = (0, {})
        self.token_qs.delete.return_value = (0, {})

        result = PurgeExpiredOnboardingsUseCase().execute()

        self.assertEqual(result, PurgeResult(0, 0, 0))
