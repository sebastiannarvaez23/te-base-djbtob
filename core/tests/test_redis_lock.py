"""Unit tests for ``core.tasks.base.redis_lock``.

The lock is a SETNX (``cache.add``) on the ``auth`` Redis cache. We
swap that backend for a per-test LocMem instance so the contract can
be exercised without a live Redis. The behaviour we pin:

  * First entry acquires the slot (yields ``True``).
  * A second entry while the first is still held is denied
    (yields ``False``).
  * On normal exit the holder releases the slot (next entry succeeds).
  * On exception the holder still releases (``finally`` semantics) —
    a crash mid-task must not leave the lock orphaned beyond its TTL.
  * A non-holder (the ``False`` branch) MUST NOT call ``delete`` —
    otherwise a noisy retry would steal the holder's slot.
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import uuid
from unittest import TestCase, mock

from django.core.cache.backends.locmem import LocMemCache

from core.tasks.base import redis_lock


def _fresh_locmem() -> LocMemCache:
    # Unique LOCATION so the process-wide LocMem registry does not
    # leak state between tests in the same suite.
    return LocMemCache(f'redis-lock-{uuid.uuid4()}', {})


class _RedisLockTestBase(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem()
        # ``caches`` is a dict-like — patch it with a real dict that
        # only contains the 'auth' key the lock reads.
        caches_patch = mock.patch(
            'core.tasks.base.caches',
            {'auth': self.cache},
        )
        caches_patch.start()
        self.addCleanup(caches_patch.stop)


class TestAcquireAndRelease(_RedisLockTestBase):

    def test_first_entry_acquires(self):
        with redis_lock('job:x', ttl_seconds=60) as acquired:
            self.assertTrue(acquired)

    def test_releases_on_normal_exit(self):
        """After the holder exits cleanly the next entry must succeed —
        otherwise back-to-back beats would always trip the skip path."""
        with redis_lock('job:x', ttl_seconds=60):
            pass
        with redis_lock('job:x', ttl_seconds=60) as acquired:
            self.assertTrue(acquired)

    def test_releases_on_exception(self):
        """``finally`` semantics: a crash inside the body must not leave
        the lock held until TTL. If this regresses, a single failure
        wedges the schedule for ``ttl_seconds``."""
        class _Boom(Exception):
            pass

        with self.assertRaises(_Boom):
            with redis_lock('job:x', ttl_seconds=60):
                raise _Boom()

        with redis_lock('job:x', ttl_seconds=60) as acquired:
            self.assertTrue(acquired)


class TestContention(_RedisLockTestBase):

    def test_concurrent_entry_is_denied(self):
        """While the lock is held, a second entry on the same key
        yields ``False`` — the caller's responsibility is to short-
        circuit, not to wait."""
        with redis_lock('job:x', ttl_seconds=60) as outer:
            self.assertTrue(outer)
            with redis_lock('job:x', ttl_seconds=60) as inner:
                self.assertFalse(inner)

    def test_denied_caller_does_not_release_holder_slot(self):
        """The non-holder branch must not call ``delete`` on the key —
        if it did, a noisy retry could 'steal' the holder's slot. We
        verify by confirming the holder's slot is still held after the
        denied caller exits."""
        with redis_lock('job:x', ttl_seconds=60) as outer:
            self.assertTrue(outer)
            with redis_lock('job:x', ttl_seconds=60) as inner:
                self.assertFalse(inner)
            # Outer is still alive — so a third entry must still be denied.
            with redis_lock('job:x', ttl_seconds=60) as third:
                self.assertFalse(third)

    def test_distinct_keys_do_not_collide(self):
        """Lock keys are namespaced; two unrelated jobs must not block
        each other."""
        with redis_lock('job:a', ttl_seconds=60) as a:
            with redis_lock('job:b', ttl_seconds=60) as b:
                self.assertTrue(a)
                self.assertTrue(b)


class TestKeyNamespace(_RedisLockTestBase):

    def test_full_key_is_prefixed_with_lock(self):
        """The lock writes under ``lock:<key>`` so its keyspace is
        distinguishable from unrelated cache entries (rate limits,
        sessions, etc.) sharing the same Redis DB. The value is a unique
        ownership token (not a constant) so a stale holder cannot delete a
        lock another worker re-acquired after the lease expired."""
        with redis_lock('job:x', ttl_seconds=60):
            token = self.cache.get('lock:job:x')
            self.assertIsInstance(token, str)
            self.assertTrue(token)

    def test_key_is_cleared_on_exit(self):
        with redis_lock('job:x', ttl_seconds=60):
            pass
        self.assertIsNone(self.cache.get('lock:job:x'))

    def test_release_does_not_steal_a_relocked_slot(self):
        """If the lease expires mid-task and another worker re-acquires the
        slot, the original holder's release must NOT delete the new owner's
        lock. We simulate the takeover by overwriting the key with a foreign
        token while the holder is still inside the context."""
        with redis_lock('job:x', ttl_seconds=60) as acquired:
            self.assertTrue(acquired)
            # A different worker acquires the slot after our lease expired.
            self.cache.set('lock:job:x', 'foreign-worker-token', timeout=60)
        # Our stale release saw a token mismatch and left the slot alone.
        self.assertEqual(self.cache.get('lock:job:x'), 'foreign-worker-token')
