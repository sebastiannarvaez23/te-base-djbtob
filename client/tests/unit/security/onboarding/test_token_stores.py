"""Unit tests for the Redis-backed onboarding token stores.

Covers:
  * issue → resolve round-trip recovers the registration UUID.
  * revoke makes a previously issued token non-resolvable (one-shot).
  * The session vs resume stores use distinct key prefixes so a leaked
    magic-link cannot be replayed as a session cookie (and vice versa).
  * Resolution of an unknown / empty / malformed token returns None
    without raising — the caller maps to ONB_INVALID_TOKEN.

The Redis cache is replaced with a LocMem instance through a module-
level patch on ``_cache``; this keeps the tests hermetic and runs
without ``django_redis`` being installed.
"""
from unittest import TestCase, mock
from uuid import uuid4

from django.core.cache.backends.locmem import LocMemCache


def _fresh_locmem() -> LocMemCache:
    import uuid as _u
    return LocMemCache(f'onb-{_u.uuid4()}', {})


class _TokenStoreTestBase(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem()
        patch = mock.patch(
            'client.features.security.lifecycle.onboarding.infrastructure.'
            'onboarding_token_store._cache',
            return_value=self.cache,
        )
        patch.start()
        self.addCleanup(patch.stop)


class TestRedisOnboardingTokenStore(_TokenStoreTestBase):

    def _store(self):
        from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
            RedisOnboardingTokenStore,
        )
        return RedisOnboardingTokenStore()

    def test_issue_then_resolve_returns_registration_id(self):
        store = self._store()
        reg_id = uuid4()

        token = store.issue(reg_id, ttl_seconds=3600)
        resolved = store.resolve(token)

        self.assertEqual(resolved, reg_id)

    def test_revoke_makes_token_unresolvable(self):
        store = self._store()
        reg_id = uuid4()
        token = store.issue(reg_id, ttl_seconds=3600)

        store.revoke(token)

        self.assertIsNone(store.resolve(token))

    def test_resolve_unknown_token_returns_none(self):
        self.assertIsNone(self._store().resolve('not-a-real-token'))

    def test_resolve_empty_string_returns_none(self):
        self.assertIsNone(self._store().resolve(''))

    def test_revoke_on_empty_token_is_noop(self):
        """Defensive: revoking an empty string should not explode on call
        sites that blindly pass request.COOKIES.get(...)."""
        self._store().revoke('')  # no exception

    def test_tokens_are_unique_per_issue(self):
        store = self._store()
        reg_id = uuid4()
        a = store.issue(reg_id, ttl_seconds=3600)
        b = store.issue(reg_id, ttl_seconds=3600)
        self.assertNotEqual(a, b)

    def test_key_uses_session_prefix(self):
        store = self._store()
        token = store.issue(uuid4(), ttl_seconds=3600)
        self.assertIsNotNone(self.cache.get(f'onb:{token}'))


class TestRedisOnboardingResumeTokenStore(_TokenStoreTestBase):

    def _store(self):
        from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
            RedisOnboardingResumeTokenStore,
        )
        return RedisOnboardingResumeTokenStore()

    def test_issue_then_resolve_returns_registration_id(self):
        store = self._store()
        reg_id = uuid4()
        token = store.issue(reg_id, ttl_seconds=7 * 86400)
        self.assertEqual(store.resolve(token), reg_id)

    def test_revoke_makes_resume_token_unresolvable(self):
        """Single-use guarantee: once the magic-link is honoured, the token
        must not resolve again even if the email is forwarded."""
        store = self._store()
        token = store.issue(uuid4(), ttl_seconds=7 * 86400)
        store.revoke(token)
        self.assertIsNone(store.resolve(token))

    def test_key_uses_resume_prefix(self):
        store = self._store()
        token = store.issue(uuid4(), ttl_seconds=7 * 86400)
        self.assertIsNotNone(self.cache.get(f'onb:resume:{token}'))


class TestSessionAndResumeStoresAreIsolated(_TokenStoreTestBase):
    """The two stores must not accept each other's tokens — a resume
    magic-link must never unlock a session cookie and vice versa."""

    def test_session_token_is_not_resolvable_via_resume_store(self):
        from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
            RedisOnboardingTokenStore,
            RedisOnboardingResumeTokenStore,
        )
        session_token = RedisOnboardingTokenStore().issue(uuid4(), ttl_seconds=3600)
        self.assertIsNone(RedisOnboardingResumeTokenStore().resolve(session_token))

    def test_resume_token_is_not_resolvable_via_session_store(self):
        from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
            RedisOnboardingTokenStore,
            RedisOnboardingResumeTokenStore,
        )
        resume_token = RedisOnboardingResumeTokenStore().issue(uuid4(), ttl_seconds=86400)
        self.assertIsNone(RedisOnboardingTokenStore().resolve(resume_token))

    def test_revoking_session_token_leaves_resume_token_alive(self):
        """Collision of raw tokens is astronomically unlikely; this test
        proves the key namespace — not the entropy — is what isolates them."""
        from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
            RedisOnboardingTokenStore,
            RedisOnboardingResumeTokenStore,
        )
        session = RedisOnboardingTokenStore()
        resume = RedisOnboardingResumeTokenStore()
        reg_id = uuid4()

        # Force the two stores to use the exact same raw token value.
        raw = 'identical-raw-token-for-test-only'
        session._cache = lambda: self.cache  # type: ignore[attr-defined]
        self.cache.set(f'onb:{raw}', str(reg_id), timeout=3600)
        self.cache.set(f'onb:resume:{raw}', str(reg_id), timeout=86400)

        session.revoke(raw)

        self.assertIsNone(session.resolve(raw))
        self.assertEqual(resume.resolve(raw), reg_id)
