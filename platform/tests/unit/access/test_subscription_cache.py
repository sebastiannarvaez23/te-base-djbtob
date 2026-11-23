"""
Unit tests for SubscriptionCache:
  - get/set subscription_id, features, limits
  - Key format with company_id
  - TTL of 5 minutes (300 seconds)
  - invalidate (single company)
  - invalidate_subscription (all companies on a plan)
  - Cache miss returns None

No Redis required — cache backend is mocked.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch, call


COMPANY_ID = str(uuid.uuid4())


# ── Subscription ID ──────────────────────────────────────────────────────────

class TestSubscriptionCacheSubscriptionId(TestCase):

    @patch('core.access.subscription._cache')
    def test_get_subscription_id_returns_cached_value(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = 'sub-abc-123'
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_subscription_id(COMPANY_ID)

        self.assertEqual(result, 'sub-abc-123')
        cache.get.assert_any_call(f'sub:{COMPANY_ID}:id')

    @patch('core.access.subscription._cache')
    def test_get_subscription_id_returns_none_on_miss(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_subscription_id(COMPANY_ID)

        self.assertIsNone(result)

    @patch('core.access.subscription._cache')
    def test_set_subscription_id_stores_with_ttl(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache, _TTL
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        SubscriptionCache.set_subscription_id(COMPANY_ID, 'sub-xyz')

        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:id', 'sub-xyz', timeout=_TTL,
        )

    @patch('core.access.subscription._cache')
    def test_set_acquisition_id_stores_with_ttl(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache, _TTL
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        SubscriptionCache.set_acquisition_id(COMPANY_ID, 'acq-xyz')

        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:acquisition', 'acq-xyz', timeout=_TTL,
        )

    @patch('core.access.subscription._cache')
    def test_get_acquisition_id_returns_cached_value(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = 'acq-abc'
        mock_cache_fn.return_value = cache

        self.assertEqual(SubscriptionCache.get_acquisition_id(COMPANY_ID), 'acq-abc')
        cache.get.assert_any_call(f'sub:{COMPANY_ID}:acquisition')

    @patch('core.access.subscription._cache')
    def test_ttl_is_300_seconds(self, mock_cache_fn):
        from core.access.subscription import _TTL
        self.assertEqual(_TTL, 300)


# ── Features ─────────────────────────────────────────────────────────────────

class TestSubscriptionCacheFeatures(TestCase):

    @patch('core.access.subscription._cache')
    def test_get_features_returns_cached_set(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = {'orders.create', 'orders.view'}
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_features(COMPANY_ID)

        self.assertEqual(result, {'orders.create', 'orders.view'})
        cache.get.assert_any_call(f'sub:{COMPANY_ID}:features')

    @patch('core.access.subscription._cache')
    def test_get_features_returns_none_on_miss(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_features(COMPANY_ID)

        self.assertIsNone(result)

    @patch('core.access.subscription._cache')
    def test_set_features_stores_with_ttl(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache, _TTL
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        features = {'orders.create', 'inventory.view'}
        SubscriptionCache.set_features(COMPANY_ID, features)

        self.assertGreaterEqual(cache.set.call_count, 1)
        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:features', features, timeout=_TTL,
        )

    @patch('core.access.subscription._cache')
    def test_set_empty_features(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        SubscriptionCache.set_features(COMPANY_ID, set())

        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:features', set(), timeout=300,
        )


# ── Limits ───────────────────────────────────────────────────────────────────

class TestSubscriptionCacheLimits(TestCase):

    @patch('core.access.subscription._cache')
    def test_get_limits_returns_cached_dict(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        limits = {
            'orders.create': {'max': 1000, 'type': 'lifetime'},
            'api.calls': {'max': 10000, 'type': 'daily'},
        }
        cache.get.return_value = limits
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_limits(COMPANY_ID)

        self.assertEqual(result['orders.create']['max'], 1000)
        self.assertEqual(result['api.calls']['type'], 'daily')
        cache.get.assert_any_call(f'sub:{COMPANY_ID}:limits')

    @patch('core.access.subscription._cache')
    def test_get_limits_returns_none_on_miss(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        result = SubscriptionCache.get_limits(COMPANY_ID)

        self.assertIsNone(result)

    @patch('core.access.subscription._cache')
    def test_set_limits_stores_with_ttl(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache, _TTL
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        limits = {'orders.create': {'max': 500, 'type': 'lifetime'}}
        SubscriptionCache.set_limits(COMPANY_ID, limits)

        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:limits', limits, timeout=_TTL,
        )

    @patch('core.access.subscription._cache')
    def test_set_empty_limits(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = 0
        mock_cache_fn.return_value = cache

        SubscriptionCache.set_limits(COMPANY_ID, {})

        cache.set.assert_any_call(
            f'sub:{COMPANY_ID}:limits', {}, timeout=300,
        )


# ── Invalidation (single company) ───────────────────────────────────────────

class TestSubscriptionCacheInvalidate(TestCase):

    @patch('core.access.subscription._cache')
    def test_invalidate_deletes_all_cache_keys(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        SubscriptionCache.invalidate(COMPANY_ID)

        cache.delete_many.assert_called_once()
        keys = cache.delete_many.call_args[0][0]
        self.assertEqual(len(keys), 6)
        self.assertIn(f'sub:{COMPANY_ID}:features', keys)
        self.assertIn(f'sub:{COMPANY_ID}:complements', keys)
        self.assertIn(f'sub:{COMPANY_ID}:limits', keys)
        self.assertIn(f'sub:{COMPANY_ID}:id', keys)
        self.assertIn(f'sub:{COMPANY_ID}:acquisition', keys)
        self.assertIn(f'sub:{COMPANY_ID}:epoch', keys)

    @patch('core.access.subscription._cache')
    def test_invalidate_different_companies_are_independent(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        c1 = str(uuid.uuid4())
        c2 = str(uuid.uuid4())

        SubscriptionCache.invalidate(c1)
        SubscriptionCache.invalidate(c2)

        self.assertEqual(cache.delete_many.call_count, 2)
        keys_c1 = cache.delete_many.call_args_list[0][0][0]
        keys_c2 = cache.delete_many.call_args_list[1][0][0]
        # No overlap
        self.assertNotEqual(keys_c1, keys_c2)


# ── Invalidation (all companies on a plan) ───────────────────────────────────

class TestSubscriptionCacheInvalidateSubscription(TestCase):

    @patch('core.access.subscription._cache')
    def test_invalidates_all_companies_on_plan(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        c1 = uuid.uuid4()
        c2 = uuid.uuid4()
        sub_id = str(uuid.uuid4())

        with patch(
            'platform.features.billing.subscription.subscription.models.CompanySubscription'
        ) as MockCS:
            MockCS.objects.filter.return_value.values_list.return_value = [c1, c2]

            SubscriptionCache.invalidate_subscription(sub_id)

        # delete_many called once per company
        self.assertEqual(cache.delete_many.call_count, 2)

    @patch('core.access.subscription._cache')
    def test_invalidate_subscription_no_companies(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        sub_id = str(uuid.uuid4())

        with patch(
            'platform.features.billing.subscription.subscription.models.CompanySubscription'
        ) as MockCS:
            MockCS.objects.filter.return_value.values_list.return_value = []

            SubscriptionCache.invalidate_subscription(sub_id)

        cache.delete_many.assert_not_called()

    @patch('core.access.subscription._cache')
    def test_invalidate_subscription_handles_db_error(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        with patch(
            'platform.features.billing.subscription.subscription.models.CompanySubscription'
        ) as MockCS:
            MockCS.objects.filter.side_effect = Exception('DB error')

            # Should not raise
            SubscriptionCache.invalidate_subscription('some-sub-id')

        cache.delete_many.assert_not_called()


# ── Key format consistency ───────────────────────────────────────────────────

class TestSubscriptionCacheKeyFormat(TestCase):

    @patch('core.access.subscription._cache')
    def test_keys_use_company_id_prefix(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        cid = 'company-abc-123'

        SubscriptionCache.get_subscription_id(cid)
        SubscriptionCache.get_features(cid)
        SubscriptionCache.get_limits(cid)

        calls = [c[0][0] for c in cache.get.call_args_list]
        self.assertIn('sub:company-abc-123:id', calls)
        self.assertIn('sub:company-abc-123:features', calls)
        self.assertIn('sub:company-abc-123:limits', calls)


# ── Catalog epoch / freshness ────────────────────────────────────────────────

class TestSubscriptionCacheCatalogEpoch(TestCase):

    @patch('core.access.subscription._cache')
    def test_bump_catalog_epoch_increments(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()
        cache.incr.return_value = 2
        mock_cache_fn.return_value = cache

        self.assertEqual(SubscriptionCache.bump_catalog_epoch(), 2)
        cache.incr.assert_called_once_with('access:catalog:epoch')

    @patch('core.access.subscription._cache')
    def test_stale_epoch_forces_features_miss(self, mock_cache_fn):
        from core.access.subscription import SubscriptionCache
        cache = MagicMock()

        def _get(key):
            if key == 'access:catalog:epoch':
                return 5
            if key == f'sub:{COMPANY_ID}:epoch':
                return 1
            if key == f'sub:{COMPANY_ID}:features':
                return {'orders.create'}
            return None

        cache.get.side_effect = _get
        mock_cache_fn.return_value = cache

        self.assertIsNone(SubscriptionCache.get_features(COMPANY_ID))


class TestInvalidateByCatalog(TestCase):

    @patch('core.access.subscription.SubscriptionCache.bump_catalog_epoch')
    @patch('core.access.subscription.SubscriptionCache.invalidate_subscription')
    def test_invalidate_by_functionality_calls_plans(self, mock_inv_sub, mock_bump):
        from core.access.subscription import SubscriptionCache
        fid = uuid.uuid4()
        sid = uuid.uuid4()

        with patch(
            'platform.features.billing.subscription.subscription.models.SubscriptionFunctionality'
        ) as MockSF:
            MockSF.objects.filter.return_value.values_list.return_value.distinct.return_value = [sid]
            SubscriptionCache.invalidate_by_functionality(fid)

        mock_inv_sub.assert_called_once_with(str(sid))
        mock_bump.assert_called_once()
