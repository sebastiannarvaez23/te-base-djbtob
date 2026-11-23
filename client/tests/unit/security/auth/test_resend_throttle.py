"""Unit tests for the email-confirmation resend throttle.

The throttle wraps ``cache.add`` (SET NX) so "one send per window" is
atomic without read-compute-write races. These tests replace the
``_cache()`` helper with a local LocMem backend so the behavior can be
exercised without a live Redis (``django_redis`` is not available in
this environment) and without cross-test state.
"""
from unittest import TestCase, mock

from django.core.cache.backends.locmem import LocMemCache


def _fresh_locmem(name: str) -> LocMemCache:
    # Unique LOCATION per instance avoids the process-wide LocMem registry
    # leaking state across tests.
    import uuid
    return LocMemCache(f'{name}-{uuid.uuid4()}', {})


class TestResendThrottle(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem('auth')
        cache_patch = mock.patch(
            'client.features.security.lifecycle.auth.application.throttle._cache',
            return_value=self.cache,
        )
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

        param_patch = mock.patch(
            'client.features.security.lifecycle.auth.application.throttle.get_parameter',
            return_value=60,
        )
        param_patch.start()
        self.addCleanup(param_patch.stop)

        from client.features.security.lifecycle.auth.application import throttle
        self.throttle = throttle

    def test_first_call_acquires_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u1'))

    def test_second_call_within_window_is_blocked(self):
        self.throttle.try_acquire_resend_slot(user_id='u1')
        self.assertFalse(self.throttle.try_acquire_resend_slot(user_id='u1'))

    def test_different_users_do_not_share_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u1'))
        self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u2'))

    def test_slot_released_after_window_expires(self):
        """Simulate TTL expiry by clearing the cache — equivalent to Redis TTL."""
        self.throttle.try_acquire_resend_slot(user_id='u1')
        self.cache.clear()
        self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u1'))

    def test_key_uses_user_id_namespace(self):
        """The cache key must include the user id so a single user is scoped."""
        self.throttle.try_acquire_resend_slot(user_id='abc-123')
        self.assertIsNotNone(self.cache.get('email_confirm_throttle:abc-123'))

    def test_window_comes_from_parameter_lookup(self):
        """If the parameter is bumped to 5s, the helper still acquires normally;
        the exact timeout is opaque but the call must succeed and persist a key."""
        with mock.patch(
            'client.features.security.lifecycle.auth.application.throttle.get_parameter',
            return_value=5,
        ):
            self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u9'))
            self.assertIsNotNone(self.cache.get('email_confirm_throttle:u9'))

    def test_set_nx_semantics_use_cache_add_not_set(self):
        """If ``.set`` were used instead of ``.add`` the throttle would silently
        reset the window on every call — guard that behavior."""
        cache_mock = mock.MagicMock()
        cache_mock.add.return_value = True
        with mock.patch(
            'client.features.security.lifecycle.auth.application.throttle._cache',
            return_value=cache_mock,
        ):
            self.throttle.try_acquire_resend_slot(user_id='u1')
        cache_mock.add.assert_called_once()
        cache_mock.set.assert_not_called()


class TestTwoFactorResendThrottle(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem('auth-2fa')
        cache_patch = mock.patch(
            'client.features.security.lifecycle.auth.application.throttle._cache',
            return_value=self.cache,
        )
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

        param_patch = mock.patch(
            'client.features.security.lifecycle.auth.application.throttle.get_parameter',
            return_value=60,
        )
        param_patch.start()
        self.addCleanup(param_patch.stop)

        from client.features.security.lifecycle.auth.application import throttle
        self.throttle = throttle

    def test_first_call_acquires_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_two_factor_resend_slot('u1'))

    def test_second_call_within_window_is_blocked(self):
        self.throttle.try_acquire_two_factor_resend_slot('u1')
        self.assertFalse(self.throttle.try_acquire_two_factor_resend_slot('u1'))
