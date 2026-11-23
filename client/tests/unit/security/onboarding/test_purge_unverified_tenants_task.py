"""Unit tests for the ``onboarding.purge_unverified_tenants`` Celery task.

The task is a thin transport-layer wrapper around
:class:`PurgeUnverifiedTenantsUseCase`. Business logic is tested in
``test_purge_unverified_tenants.py`` — here we pin the *transport*
contract:

  * The use case is constructed with the kwarg the caller passed
    (``retention_days``) and ``execute(dry_run=...)`` is invoked
    with the matching kwarg.
  * The lock is acquired under the canonical key
    ``'onboarding:purge_unverified_tenants'``.
  * Lock-acquired path returns a dict shaped
    ``{skipped: False, dry_run, retention_days, tenants_deleted, users_deleted}``
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

from client.features.security.lifecycle.onboarding.application.use_cases.purge_unverified_tenants import (
    UnverifiedTenantsPurgeResult,
)
from client.features.security.lifecycle.onboarding.tasks.purge_unverified_tenants import (
    purge_unverified_tenants,
)


_TASK_MODULE = (
    'client.features.security.lifecycle.onboarding.tasks.purge_unverified_tenants'
)


class _PurgeTaskTestBase(TestCase):
    """Shared patches: stub the use case and the redis_lock CM. Each
    test sets ``self.lock_acquired`` to drive the branch under test."""

    def setUp(self):
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

        # Use case stub: replace the class so .execute(...) is observable.
        self.use_case_instance = MagicMock()
        self.use_case_instance.execute.return_value = UnverifiedTenantsPurgeResult(
            tenants_deleted=3, users_deleted=3,
        )
        self.UseCaseClass = MagicMock(return_value=self.use_case_instance)

        uc_patch = patch(
            f'{_TASK_MODULE}.PurgeUnverifiedTenantsUseCase',
            self.UseCaseClass,
        )
        uc_patch.start()
        self.addCleanup(uc_patch.stop)


class TestLockAcquiredPath(_PurgeTaskTestBase):

    def test_returns_full_result_dict_with_counts(self):
        """The dict shape is the contract Beat / monitoring read.
        Renaming a field here is a breaking change."""
        result = purge_unverified_tenants.apply().get()

        self.assertEqual(result, {
            'skipped':         False,
            'dry_run':         False,
            'retention_days':  7,
            'tenants_deleted': 3,
            'users_deleted':   3,
        })

    def test_propagates_dry_run_to_use_case(self):
        """``dry_run`` is the operator's "preview before authorising"
        switch. If it stops reaching the use case the dry-run lies."""
        purge_unverified_tenants.apply(kwargs={'dry_run': True}).get()

        self.use_case_instance.execute.assert_called_once_with(dry_run=True)

    def test_propagates_retention_days_to_use_case_constructor(self):
        """The retention window is the only knob operators tune; if
        the kwarg never reaches the constructor, all calls collapse
        to the default (7 days) regardless of what Beat scheduled."""
        purge_unverified_tenants.apply(kwargs={'retention_days': 30}).get()

        self.UseCaseClass.assert_called_once_with(retention_days=30)

    def test_dry_run_field_echoes_input(self):
        """The returned dict echoes ``dry_run`` so the audit log line
        records what was *requested*, regardless of what the use case
        decided to do internally."""
        result = purge_unverified_tenants.apply(kwargs={'dry_run': True}).get()

        self.assertTrue(result['dry_run'])

    def test_retention_days_field_echoes_input(self):
        result = purge_unverified_tenants.apply(kwargs={'retention_days': 14}).get()

        self.assertEqual(result['retention_days'], 14)

    def test_default_dry_run_is_false(self):
        """Beat's daily call passes no kwargs — the default must be
        the destructive path (``dry_run=False``), otherwise the GC
        sweep silently never deletes anything in production."""
        purge_unverified_tenants.apply().get()

        self.use_case_instance.execute.assert_called_once_with(dry_run=False)

    def test_default_retention_days_is_7(self):
        """Same rationale as the dry_run default: Beat passes no kwargs,
        so the constructor default must produce a sensible window."""
        purge_unverified_tenants.apply().get()

        self.UseCaseClass.assert_called_once_with(retention_days=7)


class TestLockNotAcquiredPath(_PurgeTaskTestBase):

    def setUp(self):
        super().setUp()
        self.lock_acquired = False

    def test_returns_skipped_true_when_lock_held(self):
        result = purge_unverified_tenants.apply().get()

        self.assertEqual(result, {'skipped': True})

    def test_use_case_is_not_executed_when_lock_held(self):
        """The whole point of the lock is to prevent overlapping runs
        from corrupting the audit trail. If the use case still fires
        when the lock is held the protection is illusory."""
        purge_unverified_tenants.apply().get()

        self.UseCaseClass.assert_not_called()
        self.use_case_instance.execute.assert_not_called()


class TestLockKeyAndTtl(_PurgeTaskTestBase):

    def test_uses_canonical_lock_key(self):
        """The lock key is the coordination point across worker
        instances — changing it silently splits the lock into two
        independent locks and re-enables overlapping runs.

        The key is also distinct from ``onboarding:purge_expired`` on
        purpose: the two sweeps are independent and must not block
        each other."""
        purge_unverified_tenants.apply().get()

        self.assertEqual(len(self.lock_calls), 1)
        self.assertEqual(
            self.lock_calls[0]['key'],
            'onboarding:purge_unverified_tenants',
        )

    def test_ttl_is_above_soft_time_limit(self):
        """The lock TTL must exceed the task's ``soft_time_limit`` so
        a worker hitting the soft limit and being killed still leaves
        the lock to expire on its own — no orphaned locks. Soft limit
        is 600s, lock TTL is 900s."""
        purge_unverified_tenants.apply().get()

        self.assertGreater(
            self.lock_calls[0]['ttl_seconds'],
            purge_unverified_tenants.soft_time_limit,
        )
