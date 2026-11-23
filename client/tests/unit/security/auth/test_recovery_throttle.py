"""Unit tests for the password-recovery throttle slots.

Two slots protect the reset-request endpoint:

  * ``try_acquire_recovery_slot(user_id)`` — per-user window. Stops
    email-bombing a single account.
  * ``try_acquire_recovery_ip_slot(ip)`` — per-IP window. Stops a bot
    iterating email addresses from one origin.

Both wrap ``cache.add`` (SET NX) so "one slot per window" is atomic
without read-compute-write races. Tests use LocMem to exercise the
behaviour without a live Redis.
"""
import uuid
from unittest import TestCase, mock

from django.core.cache.backends.locmem import LocMemCache


def _fresh_locmem(name: str) -> LocMemCache:
    return LocMemCache(f'{name}-{uuid.uuid4()}', {})


# ── Per-user slot ────────────────────────────────────────────────────────────

class TestRecoveryUserSlot(TestCase):

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
        self.assertTrue(self.throttle.try_acquire_recovery_slot(user_id='u1'))

    def test_second_call_within_window_is_blocked(self):
        self.throttle.try_acquire_recovery_slot(user_id='u1')
        self.assertFalse(self.throttle.try_acquire_recovery_slot(user_id='u1'))

    def test_different_users_do_not_share_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_recovery_slot(user_id='u1'))
        self.assertTrue(self.throttle.try_acquire_recovery_slot(user_id='u2'))

    def test_slot_released_after_window_expires(self):
        self.throttle.try_acquire_recovery_slot(user_id='u1')
        self.cache.clear()
        self.assertTrue(self.throttle.try_acquire_recovery_slot(user_id='u1'))

    def test_key_uses_user_id_namespace(self):
        self.throttle.try_acquire_recovery_slot(user_id='abc-123')
        self.assertIsNotNone(self.cache.get('password_recovery_throttle:abc-123'))

    def test_user_and_confirmation_slots_do_not_collide(self):
        """Email-confirmation and password-recovery share the cache but
        use distinct key prefixes; activity on one must not exhaust the
        other."""
        self.throttle.try_acquire_recovery_slot(user_id='u1')
        # The confirmation throttle should still be free.
        self.assertTrue(self.throttle.try_acquire_resend_slot(user_id='u1'))

    def test_set_nx_semantics_use_cache_add_not_set(self):
        """``.set`` would silently extend the window on every call —
        guard the SETNX semantics."""
        cache_mock = mock.MagicMock()
        cache_mock.add.return_value = True
        with mock.patch(
            'client.features.security.lifecycle.auth.application.throttle._cache',
            return_value=cache_mock,
        ):
            self.throttle.try_acquire_recovery_slot(user_id='u1')
        cache_mock.add.assert_called_once()
        cache_mock.set.assert_not_called()


# ── Per-IP slot ──────────────────────────────────────────────────────────────

class TestRecoveryIpSlot(TestCase):

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
            return_value=30,
        )
        param_patch.start()
        self.addCleanup(param_patch.stop)

        from client.features.security.lifecycle.auth.application import throttle
        self.throttle = throttle

    def test_first_call_acquires_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot('203.0.113.5'))

    def test_second_call_within_window_is_blocked(self):
        self.throttle.try_acquire_recovery_ip_slot('203.0.113.5')
        self.assertFalse(self.throttle.try_acquire_recovery_ip_slot('203.0.113.5'))

    def test_different_ips_do_not_share_the_slot(self):
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot('203.0.113.5'))
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot('198.51.100.7'))

    def test_empty_ip_does_not_block(self):
        """If the request meta lacks a REMOTE_ADDR we don't have a key
        to namespace on; failing open is safer than failing closed (a
        DoS surface for misconfigured proxies)."""
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot(''))
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot(''))

    def test_none_ip_does_not_block(self):
        self.assertTrue(self.throttle.try_acquire_recovery_ip_slot(None))

    def test_empty_ip_does_not_touch_cache(self):
        """Falsy IPs must short-circuit BEFORE the cache call, otherwise
        a missing REMOTE_ADDR globally consumes the empty-string slot."""
        cache_mock = mock.MagicMock()
        with mock.patch(
            'client.features.security.lifecycle.auth.application.throttle._cache',
            return_value=cache_mock,
        ):
            self.throttle.try_acquire_recovery_ip_slot('')
        cache_mock.add.assert_not_called()

    def test_key_uses_ip_namespace(self):
        self.throttle.try_acquire_recovery_ip_slot('203.0.113.5')
        self.assertIsNotNone(self.cache.get('password_recovery_throttle_ip:203.0.113.5'))

    def test_ip_and_user_slots_do_not_collide(self):
        self.throttle.try_acquire_recovery_ip_slot('203.0.113.5')
        self.assertTrue(self.throttle.try_acquire_recovery_slot(user_id='203.0.113.5'))
