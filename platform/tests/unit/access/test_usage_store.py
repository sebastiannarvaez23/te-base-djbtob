"""
Unit tests for UsageStore (Redis counters):
  - Key format (daily with date, lifetime without)
  - get_daily / get_lifetime (read counters)
  - increment_daily / increment_lifetime (atomic increment)
  - decrement_lifetime (atomic decrement with floor at 0)
  - set_lifetime (warmup seeding)
  - reset_lifetime / reset_all_company (admin cleanup)
  - First-increment creates key with correct TTL
  - Decrement of non-existent key returns 0

No Redis required — cache backend is mocked.
"""
import uuid
from datetime import date
from unittest import TestCase
from unittest.mock import MagicMock, patch


COMPANY_ID = str(uuid.uuid4())
FEATURE_KEY = 'orders.create'


# ── Key format ───────────────────────────────────────────────────────────────

class TestUsageStoreKeyFormat(TestCase):

    def test_daily_key_includes_date(self):
        from core.access.store import UsageStore
        key = UsageStore._daily_key(COMPANY_ID, FEATURE_KEY)

        today = date.today().isoformat()
        self.assertIn(COMPANY_ID, key)
        self.assertIn(FEATURE_KEY, key)
        self.assertIn('daily', key)
        self.assertIn(today, key)

    def test_lifetime_key_has_no_date(self):
        from core.access.store import UsageStore
        key = UsageStore._lifetime_key(COMPANY_ID, FEATURE_KEY)

        self.assertIn(COMPANY_ID, key)
        self.assertIn(FEATURE_KEY, key)
        self.assertIn('lifetime', key)
        self.assertNotIn(date.today().isoformat(), key)

    def test_daily_keys_differ_per_company(self):
        from core.access.store import UsageStore
        c1 = str(uuid.uuid4())
        c2 = str(uuid.uuid4())

        k1 = UsageStore._daily_key(c1, FEATURE_KEY)
        k2 = UsageStore._daily_key(c2, FEATURE_KEY)

        self.assertNotEqual(k1, k2)

    def test_lifetime_keys_differ_per_feature(self):
        from core.access.store import UsageStore

        k1 = UsageStore._lifetime_key(COMPANY_ID, 'orders.create')
        k2 = UsageStore._lifetime_key(COMPANY_ID, 'orders.view')

        self.assertNotEqual(k1, k2)


# ── get_daily / get_lifetime ─────────────────────────────────────────────────

class TestUsageStoreRead(TestCase):

    @patch('core.access.store._cache')
    def test_get_daily_returns_cached_value(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 42
        mock_cache_fn.return_value = cache

        result = UsageStore.get_daily(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 42)

    @patch('core.access.store._cache')
    def test_get_daily_returns_zero_when_missing(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 0  # default
        mock_cache_fn.return_value = cache

        result = UsageStore.get_daily(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)

    @patch('core.access.store._cache')
    def test_get_lifetime_returns_cached_value(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 500
        mock_cache_fn.return_value = cache

        result = UsageStore.get_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 500)

    @patch('core.access.store._cache')
    def test_get_lifetime_returns_zero_when_missing(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        result = UsageStore.get_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)


# ── get_lifetime self-heal (re-siembra en miss) ───────────────────────────────

class TestUsageStoreLifetimeSelfHeal(TestCase):
    """En un miss real (clave inexistente: evicción / FLUSHDB / reinicio) el
    contador se re-siembra desde la BD si hay un counter registrado."""

    @patch('core.access.store._cache')
    def test_reseeds_from_db_on_miss_when_counter_registered(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = None  # miss real (None, no 0)
        mock_cache_fn.return_value = cache

        with patch('core.access.registry.usage_registry') as mock_reg:
            mock_reg.get_count.return_value = 7
            result = UsageStore.get_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 7)
        # Re-sembró el valor real en Redis (sin TTL).
        cache.set.assert_called_once()
        args = cache.set.call_args
        self.assertEqual(args[0][1], 7)

    @patch('core.access.store._cache')
    def test_returns_zero_on_miss_without_registered_counter(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        with patch('core.access.registry.usage_registry') as mock_reg:
            mock_reg.get_count.return_value = None  # sin counter → no reconstruible
            result = UsageStore.get_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)
        cache.set.assert_not_called()


# ── increment_daily ──────────────────────────────────────────────────────────

class TestUsageStoreIncrementDaily(TestCase):

    @patch('core.access.store._cache')
    def test_increment_existing_key(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.return_value = 43
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_daily(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 43)
        cache.incr.assert_called_once()

    @patch('core.access.store._cache')
    def test_increment_creates_key_on_first_use(self, mock_cache_fn):
        from core.access.store import UsageStore, _DAILY_TTL
        cache = MagicMock()
        cache.incr.side_effect = ValueError('Key does not exist')
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_daily(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 1)
        cache.set.assert_called_once()
        # Verify TTL is set (48 hours)
        args = cache.set.call_args
        self.assertEqual(args[0][1], 1)
        self.assertEqual(args[1].get('timeout') or args[0][2], _DAILY_TTL)

    @patch('core.access.store._cache')
    def test_increment_returns_zero_when_redis_unavailable(self, mock_cache_fn):
        """Con IGNORE_EXCEPTIONS=True, incr retorna None en un outage; el
        contrato -> int se respeta normalizando a 0 (no None)."""
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.return_value = None
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_daily(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)
        cache.set.assert_not_called()


# ── increment_lifetime ───────────────────────────────────────────────────────

class TestUsageStoreIncrementLifetime(TestCase):

    @patch('core.access.store._cache')
    def test_increment_existing_key(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.return_value = 501
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 501)

    @patch('core.access.store._cache')
    def test_increment_creates_key_without_ttl(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.side_effect = ValueError('Key does not exist')
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 1)
        cache.set.assert_called_once()
        args = cache.set.call_args
        self.assertEqual(args[0][1], 1)
        # Lifetime keys have no TTL (timeout=None)
        self.assertIsNone(args[1].get('timeout') if args[1] else args[0][2])


# ── decrement_lifetime ───────────────────────────────────────────────────────

class TestUsageStoreDecrementLifetime(TestCase):

    @patch('core.access.store._cache')
    def test_decrement_existing_key(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.decr.return_value = 499
        mock_cache_fn.return_value = cache

        result = UsageStore.decrement_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 499)

    @patch('core.access.store._cache')
    def test_decrement_floors_at_zero(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.decr.return_value = -1  # went below zero
        mock_cache_fn.return_value = cache

        result = UsageStore.decrement_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)
        # Should reset to 0
        cache.set.assert_called_once()

    @patch('core.access.store._cache')
    def test_decrement_nonexistent_key_returns_zero(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.decr.side_effect = ValueError('Key does not exist')
        mock_cache_fn.return_value = cache

        result = UsageStore.decrement_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)

    @patch('core.access.store._cache')
    def test_decrement_returns_zero_when_redis_unavailable(self, mock_cache_fn):
        """decr retorna None en un outage (IGNORE_EXCEPTIONS); no debe reventar
        con TypeError al comparar None < 0."""
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.decr.return_value = None
        mock_cache_fn.return_value = cache

        result = UsageStore.decrement_lifetime(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 0)
        cache.set.assert_not_called()


# ── set_lifetime (warmup seeding) ────────────────────────────────────────────

class TestUsageStoreSetLifetime(TestCase):

    @patch('core.access.store._cache')
    def test_set_lifetime_seeds_value(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        UsageStore.set_lifetime(COMPANY_ID, FEATURE_KEY, 42)

        cache.set.assert_called_once()
        args = cache.set.call_args
        self.assertEqual(args[0][1], 42)
        # No TTL for lifetime
        self.assertIsNone(args[1].get('timeout') if args[1] else args[0][2])

    @patch('core.access.store._cache')
    def test_set_lifetime_with_zero(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        UsageStore.set_lifetime(COMPANY_ID, FEATURE_KEY, 0)

        cache.set.assert_called_once()
        args = cache.set.call_args
        self.assertEqual(args[0][1], 0)


# ── reset_lifetime / reset_all_company ───────────────────────────────────────

class TestUsageStoreReset(TestCase):

    @patch('core.access.store._cache')
    def test_reset_lifetime_deletes_key(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        UsageStore.reset_lifetime(COMPANY_ID, FEATURE_KEY)

        cache.delete.assert_called_once()

    @patch('core.access.store._cache')
    def test_reset_all_company_uses_pattern_delete(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        UsageStore.reset_all_company(COMPANY_ID)

        cache.delete_pattern.assert_called_once_with(f'usage:{COMPANY_ID}:*')

    @patch('core.access.store._cache')
    def test_reset_all_company_handles_no_pattern_support(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.delete_pattern = MagicMock(side_effect=AttributeError)
        mock_cache_fn.return_value = cache

        # Should not raise
        UsageStore.reset_all_company(COMPANY_ID)


# ── Window counters ──────────────────────────────────────────────────────────

class TestUsageStoreWindowSlot(TestCase):

    def test_slot_is_stable_inside_the_period(self):
        from core.access.store import UsageStore
        self.assertEqual(UsageStore.window_slot(3, now=0), UsageStore.window_slot(3, now=10799))

    def test_slot_advances_when_period_ends(self):
        from core.access.store import UsageStore
        self.assertEqual(UsageStore.window_slot(3, now=0) + 1, UsageStore.window_slot(3, now=10800))

    def test_three_hour_window_has_eight_slots_per_day(self):
        from core.access.store import UsageStore
        slots = {UsageStore.window_slot(3, now=t) for t in range(0, 24 * 3600, 60)}
        self.assertEqual(len(slots), 8)

    def test_window_key_includes_hours_and_slot(self):
        from core.access.store import UsageStore
        key = UsageStore._window_key(COMPANY_ID, FEATURE_KEY, 3, now=0)
        self.assertEqual(key, f'usage:{COMPANY_ID}:{FEATURE_KEY}:window:3h:0')

    def test_window_ttl_is_remaining_plus_one_hour(self):
        from core.access.store import UsageStore
        self.assertEqual(UsageStore._window_ttl(3, now=0), 3 * 3600 + 3600)
        self.assertEqual(UsageStore._window_ttl(3, now=1), 3 * 3600 - 1 + 3600)

    def test_window_reset_at_is_start_of_next_slot(self):
        from datetime import datetime, timezone
        from core.access.store import UsageStore
        self.assertEqual(
            UsageStore.window_reset_at(3, now=0),
            datetime(1970, 1, 1, 3, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            UsageStore.window_reset_at(3, now=10799),
            datetime(1970, 1, 1, 3, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            UsageStore.window_reset_at(3, now=10800),
            datetime(1970, 1, 1, 6, 0, tzinfo=timezone.utc),
        )

    def test_window_hours_zero_raises(self):
        from core.access.store import UsageStore
        with self.assertRaises(ValueError):
            UsageStore.window_slot(0)

    def test_window_hours_none_raises(self):
        from core.access.store import UsageStore
        with self.assertRaises(ValueError):
            UsageStore.window_slot(None)


class TestUsageStoreWindowRead(TestCase):

    @patch('core.access.store._cache')
    def test_get_window_returns_cached_value(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 2
        mock_cache_fn.return_value = cache

        result = UsageStore.get_window(COMPANY_ID, FEATURE_KEY, 3)

        self.assertEqual(result, 2)

    @patch('core.access.store._cache')
    def test_get_window_returns_zero_when_missing(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        result = UsageStore.get_window(COMPANY_ID, FEATURE_KEY, 3)

        self.assertEqual(result, 0)


class TestUsageStoreIncrementWindow(TestCase):

    @patch('core.access.store._cache')
    def test_increment_existing_key(self, mock_cache_fn):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.return_value = 2
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_window(COMPANY_ID, FEATURE_KEY, 3)

        self.assertEqual(result, 2)
        cache.incr.assert_called_once()

    @patch('core.access.store.time.time', return_value=0)
    @patch('core.access.store._cache')
    def test_increment_creates_key_on_first_use_with_ttl(self, mock_cache_fn, _mock_time):
        from core.access.store import UsageStore
        cache = MagicMock()
        cache.incr.side_effect = ValueError('Key does not exist')
        mock_cache_fn.return_value = cache

        result = UsageStore.increment_window(COMPANY_ID, FEATURE_KEY, 3)

        self.assertEqual(result, 1)
        cache.set.assert_called_once_with(
            f'usage:{COMPANY_ID}:{FEATURE_KEY}:window:3h:0',
            1,
            timeout=3 * 3600 + 3600,
        )
