"""Unit tests for MAX_LOGIN_RETRIES lockout.

The retry store is swapped for LocMem so the suite does not need Redis.
"""
from unittest import TestCase, mock
from unittest.mock import MagicMock

from django.core.cache.backends.locmem import LocMemCache

import pytest

from core.errors import AppErrorCode, AuthException
from core.errors.codes import ERROR_REGISTRY


pytestmark = pytest.mark.unit


def _fresh_locmem(name: str) -> LocMemCache:
    import uuid
    return LocMemCache(f'{name}-{uuid.uuid4()}', {})


LOCKOUT = 'client.features.security.lifecycle.auth.application.login_lockout'
STORE = 'core.auth.login_retry_store'


class TestLoginLockedErrorRegistry(TestCase):

    def test_auth_017_is_429(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_LOGIN_LOCKED]
        self.assertEqual(AppErrorCode.AUTH_LOGIN_LOCKED.value, 'AUTH_017')
        self.assertEqual(entry['http_status'], 429)
        self.assertIn('locked', entry['message'].lower())


class TestMaxRetriesParsing(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import login_lockout as lockout
        self.lockout = lockout

    def test_zero_and_false_disable(self):
        for raw in (0, False, None, '0'):
            with mock.patch(f'{LOCKOUT}.get_parameter', return_value=raw):
                self.assertEqual(self.lockout.max_retries(), 0)

    def test_true_uses_configured_default(self):
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=True):
            self.assertEqual(self.lockout.max_retries(), 4)

    def test_int_value(self):
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=4):
            self.assertEqual(self.lockout.max_retries(), 4)

    def test_garbage_disables(self):
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value='nope'):
            self.assertEqual(self.lockout.max_retries(), 0)


class TestLoginLockoutUseCase(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem('login-lockout')
        cache_patch = mock.patch(f'{STORE}._cache', return_value=self.cache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

        param_patch = mock.patch(f'{LOCKOUT}.get_parameter', return_value=4)
        param_patch.start()
        self.addCleanup(param_patch.stop)

        schema_patch = mock.patch(f'{STORE}.schema_name', return_value='acme')
        schema_patch.start()
        self.addCleanup(schema_patch.stop)

        from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout
        from client.features.security.lifecycle.auth.application.use_cases import LoginUserUseCase
        from client.features.security.lifecycle.auth.infrastructure.login_retry_store import (
            CacheLoginRetryStore,
        )
        self.mock_repo = MagicMock()
        self.use_case = LoginUserUseCase(
            self.mock_repo,
            LoginLockout(CacheLoginRetryStore()),
        )

    def _fail_password(self):
        self.mock_repo.authenticate.side_effect = AuthException(
            AppErrorCode.AUTH_INVALID_CREDENTIALS,
        )

    def test_first_failures_stay_auth_001(self):
        self._fail_password()
        for _ in range(3):
            with self.assertRaises(AuthException) as ctx:
                self.use_case.execute('jsmith', 'wrong')
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_nth_failure_locks(self):
        self._fail_password()
        for _ in range(3):
            with self.assertRaises(AuthException):
                self.use_case.execute('jsmith', 'wrong')
        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'wrong')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)
        self.assertEqual(ctx.exception.http_status, 429)
        self.assertIsNone(ctx.exception.retry_after)

    def test_locked_rejects_even_with_correct_password(self):
        self._fail_password()
        for _ in range(4):
            with self.assertRaises(AuthException):
                self.use_case.execute('jsmith', 'wrong')
        self.mock_repo.authenticate.reset_mock()
        self.mock_repo.authenticate.side_effect = None
        self.mock_repo.authenticate.return_value = MagicMock(username='jsmith')
        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'correct')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)
        self.assertIsNone(ctx.exception.retry_after)
        self.mock_repo.authenticate.assert_not_called()

    def test_success_clears_the_counter(self):
        self._fail_password()
        for _ in range(3):
            with self.assertRaises(AuthException):
                self.use_case.execute('jsmith', 'wrong')
        from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient
        from core.access.billing_recovery import LoginAccessResult

        user = MagicMock(username='jsmith')
        self.mock_repo.authenticate.side_effect = None
        auth = AuthenticatedClient(user=user, access=LoginAccessResult(mode='full'))
        self.mock_repo.authenticate.return_value = auth
        self.assertIs(self.use_case.execute('jsmith', 'correct'), auth)
        self._fail_password()
        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'wrong')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_unknown_username_counts_toward_lockout(self):
        self._fail_password()
        for _ in range(4):
            with self.assertRaises(AuthException) as ctx:
                self.use_case.execute('ghost', 'wrong')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)

    def test_inactive_account_does_not_increment(self):
        self.mock_repo.authenticate.side_effect = AuthException(
            AppErrorCode.AUTH_ACCOUNT_INACTIVE,
        )
        for _ in range(5):
            with self.assertRaises(AuthException) as ctx:
                self.use_case.execute('jsmith', 'pass1234')
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)
        self._fail_password()
        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('jsmith', 'wrong')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_usernames_are_isolated(self):
        self._fail_password()
        for _ in range(4):
            with self.assertRaises(AuthException):
                self.use_case.execute('alice', 'wrong')
        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute('bob', 'wrong')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_schemas_are_isolated(self):
        self._fail_password()
        for _ in range(4):
            with self.assertRaises(AuthException):
                self.use_case.execute('jsmith', 'wrong')
        with mock.patch(f'{STORE}.schema_name', return_value='other'):
            with self.assertRaises(AuthException) as ctx:
                self.use_case.execute('jsmith', 'wrong')
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_disabled_policy_never_locks(self):
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=0):
            self._fail_password()
            for _ in range(8):
                with self.assertRaises(AuthException) as ctx:
                    self.use_case.execute('jsmith', 'wrong')
                self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_cache_down_fail_open(self):
        broken = mock.MagicMock()
        broken.get.side_effect = RuntimeError('redis down')
        broken.incr.side_effect = RuntimeError('redis down')
        broken.add.side_effect = RuntimeError('redis down')
        broken.delete.side_effect = RuntimeError('redis down')
        with mock.patch(f'{STORE}._cache', return_value=broken):
            self._fail_password()
            with self.assertRaises(AuthException) as ctx:
                self.use_case.execute('jsmith', 'wrong')
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)
            user = MagicMock(username='jsmith')
            self.mock_repo.authenticate.side_effect = None
            from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient
            from core.access.billing_recovery import LoginAccessResult
            auth = AuthenticatedClient(user=user, access=LoginAccessResult(mode='full'))
            self.mock_repo.authenticate.return_value = auth
            self.assertIs(self.use_case.execute('jsmith', 'ok'), auth)


class _StubRetryStore:
    """Minimal ILoginRetryStore for lockout retry_after tests."""

    def __init__(self, *, failures=4, remaining=42, ttl_error=False):
        self.failures = failures
        self.remaining = remaining
        self.ttl_error = ttl_error
        self.ttl_calls = 0

    def incr_failures(self, username, ttl_seconds):
        return self.failures

    def get_failures(self, username):
        return self.failures

    def refresh_ttl(self, username, count, ttl_seconds):
        return None

    def clear_failures(self, username):
        return None

    def ttl_remaining(self, username):
        self.ttl_calls += 1
        if self.ttl_error:
            raise RuntimeError('ttl down')
        return self.remaining


class TestLoginLockoutRetryAfterPort(TestCase):

    def test_uses_store_ttl_remaining(self):
        from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout

        store = _StubRetryStore(remaining=42)
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=4):
            with self.assertRaises(AuthException) as ctx:
                LoginLockout(store).assert_not_locked('jane')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)
        self.assertEqual(ctx.exception.retry_after, 42)
        self.assertEqual(store.ttl_calls, 1)

    def test_ttl_read_failure_still_locks_without_inventing_wait(self):
        from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout

        store = _StubRetryStore(ttl_error=True)
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=4):
            with self.assertRaises(AuthException) as ctx:
                LoginLockout(store).assert_not_locked('jane')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)
        self.assertIsNone(ctx.exception.retry_after)
        self.assertEqual(store.ttl_calls, 1)

    def test_store_ttl_is_ceiled(self):
        from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout

        store = _StubRetryStore(remaining=12.2)
        with mock.patch(f'{LOCKOUT}.get_parameter', return_value=4):
            with self.assertRaises(AuthException) as ctx:
                LoginLockout(store).assert_not_locked('jane')
        self.assertEqual(ctx.exception.retry_after, 13)


class TestLoginRetryStore(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem('login-retry-store')
        cache_patch = mock.patch(f'{STORE}._cache', return_value=self.cache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        schema_patch = mock.patch(f'{STORE}.schema_name', return_value='acme')
        schema_patch.start()
        self.addCleanup(schema_patch.stop)
        from client.features.security.lifecycle.auth.infrastructure import login_retry_store as store
        self.store = store

    def test_incr_counts_up(self):
        self.assertEqual(self.store.incr_failures('Jane', 60), 1)
        self.assertEqual(self.store.incr_failures('jane', 60), 2)
        self.assertEqual(self.store.get_failures('JANE'), 2)

    def test_clear_resets(self):
        self.store.incr_failures('jane', 60)
        self.store.clear_failures('jane')
        self.assertEqual(self.store.get_failures('jane'), 0)

    def test_ttl_remaining_without_backend_ttl_is_none(self):
        self.store.incr_failures('jane', 60)
        self.assertIsNone(self.store.ttl_remaining('jane'))

    def test_ttl_remaining_empty_username_is_none(self):
        self.assertIsNone(self.store.ttl_remaining(''))
        self.assertIsNone(self.store.ttl_remaining('   '))

    def test_ttl_remaining_prefers_cache_ttl(self):
        backend = mock.MagicMock()
        backend.ttl.return_value = 7.1
        with mock.patch(f'{STORE}._cache', return_value=backend):
            self.assertEqual(self.store.ttl_remaining('jane'), 8)
        backend.ttl.assert_called_once()
