"""Unit tests for the ``onboarding.purge_expired`` Celery task.

The task is a thin transport-layer wrapper around
:class:`PurgeExpiredOnboardingsUseCase`. Business logic is tested in
``test_purge_expired_use_case.py`` — here we pin the *transport*
contract:

  * The use case step methods are called when the lock is acquired.
  * The lock is acquired under the canonical key
    ``'onboarding:purge_expired'``.
  * Lock-acquired path returns a dict shaped
    ``{skipped: False, dry_run, expired, failed_deleted, tokens_deleted}``
    so the Beat log / monitoring downstream has stable fields to read.
  * Lock-not-acquired path short-circuits to ``{'skipped': True}`` —
    the use case must NOT execute (otherwise the lock buys nothing).
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.tasks.progress_port import (
    get_task_progress_reporter,
    set_task_progress_reporter,
)
from client.features.security.lifecycle.onboarding.tasks.purge import (
    purge_expired_onboardings,
)


_TASK_MODULE = 'client.features.security.lifecycle.onboarding.tasks.purge'


class _PurgeTaskTestBase(TestCase):
    """Shared patches: stub the use case and the redis_lock CM. Each
    test sets ``self.lock_acquired`` to drive the branch under test."""

    def setUp(self):
        self._prev_reporter = get_task_progress_reporter()
        set_task_progress_reporter(None)
        self.addCleanup(lambda: set_task_progress_reporter(self._prev_reporter))

        self.lock_acquired = True
        # Track which key/ttl the task asked for so we can assert on it.
        self.lock_calls: list = []

        @contextmanager
        def _fake_lock(key, ttl_seconds):
            self.lock_calls.append({'key': key, 'ttl_seconds': ttl_seconds})
            yield self.lock_acquired

        lock_patch = patch(f'{_TASK_MODULE}.redis_lock', side_effect=_fake_lock)
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        self.use_case_instance = MagicMock()
        self.use_case_instance.failed_retention_days = 30
        self.use_case_instance.token_retention_days = 7
        self.use_case_instance.expire_in_progress.return_value = 4
        self.use_case_instance.delete_old_failed.return_value = 2
        self.use_case_instance.delete_old_tokens.return_value = 7
        self.UseCaseClass = MagicMock(return_value=self.use_case_instance)

        uc_patch = patch(
            f'{_TASK_MODULE}.PurgeExpiredOnboardingsUseCase',
            self.UseCaseClass,
        )
        uc_patch.start()
        self.addCleanup(uc_patch.stop)


class TestLockAcquiredPath(_PurgeTaskTestBase):

    def test_returns_full_result_dict_with_counts(self):
        """The dict shape is the contract Beat / monitoring read.
        Renaming a field here is a breaking change."""
        result = purge_expired_onboardings.apply().get()

        self.assertEqual(result, {
            'skipped':        False,
            'dry_run':        False,
            'expired':        4,
            'failed_deleted': 2,
            'tokens_deleted': 7,
        })

    def test_propagates_dry_run_to_use_case(self):
        """``dry_run`` is the operator's "preview before authorising"
        switch. If it stops reaching the use case the dry-run lies."""
        purge_expired_onboardings.apply(kwargs={'dry_run': True}).get()

        self.use_case_instance.expire_in_progress.assert_called_once()
        self.assertTrue(self.use_case_instance.expire_in_progress.call_args.args[1])
        self.use_case_instance.delete_old_failed.assert_called_once()
        self.assertTrue(self.use_case_instance.delete_old_failed.call_args.args[1])
        self.use_case_instance.delete_old_tokens.assert_called_once()
        self.assertTrue(self.use_case_instance.delete_old_tokens.call_args.args[1])

    def test_dry_run_field_echoes_input(self):
        """The returned dict echoes ``dry_run`` so the audit log line
        records what was *requested*, regardless of what the use case
        decided to do internally."""
        result = purge_expired_onboardings.apply(kwargs={'dry_run': True}).get()

        self.assertTrue(result['dry_run'])

    def test_default_dry_run_is_false(self):
        """Beat's daily call passes no kwargs — the default must be
        the destructive path (``dry_run=False``), otherwise the GC
        sweep silently never deletes anything in production."""
        purge_expired_onboardings.apply().get()

        self.assertFalse(self.use_case_instance.expire_in_progress.call_args.args[1])


class TestLockNotAcquiredPath(_PurgeTaskTestBase):

    def setUp(self):
        super().setUp()
        self.lock_acquired = False

    def test_returns_skipped_true_when_lock_held(self):
        result = purge_expired_onboardings.apply().get()

        self.assertEqual(result, {'skipped': True})

    def test_use_case_is_not_executed_when_lock_held(self):
        """The whole point of the lock is to prevent overlapping runs
        from corrupting the audit trail. If the use case still fires
        when the lock is held the protection is illusory."""
        purge_expired_onboardings.apply().get()

        self.UseCaseClass.assert_not_called()
        self.use_case_instance.expire_in_progress.assert_not_called()


class TestLockKeyAndTtl(_PurgeTaskTestBase):

    def test_uses_canonical_lock_key(self):
        """The lock key is the coordination point across worker
        instances — changing it silently splits the lock into two
        independent locks and re-enables overlapping runs."""
        purge_expired_onboardings.apply().get()

        self.assertEqual(len(self.lock_calls), 1)
        self.assertEqual(self.lock_calls[0]['key'], 'onboarding:purge_expired')

    def test_ttl_is_above_soft_time_limit(self):
        """The lock TTL must exceed the task's ``soft_time_limit`` so
        a worker hitting the soft limit and being killed still leaves
        the lock to expire on its own — no orphaned locks. Soft limit
        is 600s, lock TTL is 900s."""
        purge_expired_onboardings.apply().get()

        self.assertGreater(
            self.lock_calls[0]['ttl_seconds'],
            purge_expired_onboardings.soft_time_limit,
        )
