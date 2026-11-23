"""
Unit tests for warmup_subscription_cache (initial Redis loading):
  - Redis connectivity check
  - Loads subscription_id, features, and limits for active companies
  - Seeds lifetime counters from DB via usage_registry
  - Handles no active subscriptions gracefully
  - Handles Redis unavailability gracefully
  - Reuses plan data across companies on the same subscription
  - Only seeds counters for lifetime limits (not daily)
  - Only seeds counters with registered counter functions

No Redis or database required — all dependencies mocked.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _active_sub(company_id=None, subscription_id=None, acquisition_id=None):
    return (
        company_id or uuid.uuid4(),
        subscription_id or uuid.uuid4(),
        acquisition_id or uuid.uuid4(),
    )


# ── Redis connectivity ───────────────────────────────────────────────────────

class TestWarmupRedisCheck(TestCase):

    @patch('core.access.warmup.caches')
    @patch('core.access.warmup._register_counters')
    def test_redis_unavailable_aborts_warmup(self, mock_reg, mock_caches):
        from core.access.warmup import warmup_subscription_cache

        cache = MagicMock()
        cache.set.side_effect = Exception('Connection refused')
        mock_caches.__getitem__.return_value = cache

        # Should not raise
        warmup_subscription_cache()

    @patch('core.access.warmup._check_redis', return_value=False)
    @patch('core.access.warmup._register_counters')
    def test_redis_check_failure_logs_warning_and_returns(self, mock_reg, mock_check):
        from core.access.warmup import warmup_subscription_cache

        # Should not raise — graceful degradation
        warmup_subscription_cache()

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    def test_redis_check_success_proceeds(self, mock_reg, mock_check):
        """When Redis is available, warmup attempts to load data."""
        from core.access.warmup import warmup_subscription_cache

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:
            MockCS.objects.filter.return_value.values_list.return_value = []

            warmup_subscription_cache()


# ── Loading subscription data ────────────────────────────────────────────────

_COMPLEMENT_KEYS = (
    'platform.features.billing.complement.entitlement.infrastructure.active'
    '.active_complement_keys_by_company'
)


class TestWarmupLoadSubscriptionData(TestCase):

    def setUp(self):
        super().setUp()
        self._complement = patch(_COMPLEMENT_KEYS, return_value={})
        self._complement.start()
        self.addCleanup(self._complement.stop)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    def test_loads_subscription_id_per_company(self, MockCache, mock_reg, mock_check):
        company1 = uuid.uuid4()
        company2 = uuid.uuid4()
        sub_id = uuid.uuid4()

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company1, sub_id),
                _active_sub(company2, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['orders.create']
            MockSL.objects.filter.return_value.select_related.return_value = []

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        # Should have cached subscription_id for both companies
        calls = MockCache.set_subscription_id.call_args_list
        self.assertEqual(len(calls), 2)
        company_ids_cached = {c[0][0] for c in calls}
        self.assertIn(str(company1), company_ids_cached)
        self.assertIn(str(company2), company_ids_cached)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    def test_loads_features_into_cache(self, MockCache, mock_reg, mock_check):
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = [
                'orders.create', 'orders.view',
            ]
            MockSL.objects.filter.return_value.select_related.return_value = []

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockCache.set_features.assert_called_once()
        features_arg = MockCache.set_features.call_args[0][1]
        self.assertIn('orders.create', features_arg)
        self.assertIn('orders.view', features_arg)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    def test_loads_limits_into_cache(self, MockCache, mock_reg, mock_check):
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'orders.create'
        limit_obj.max_value = 1000
        limit_obj.validation_type = 'lifetime'

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['orders.create']
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockCache.set_limits.assert_called_once()
        limits_arg = MockCache.set_limits.call_args[0][1]
        self.assertIn('orders.create', limits_arg)
        self.assertEqual(limits_arg['orders.create']['max'], 1000)
        self.assertEqual(limits_arg['orders.create']['type'], 'lifetime')


# ── No active subscriptions ──────────────────────────────────────────────────

class TestWarmupNoActiveSubscriptions(TestCase):

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    def test_handles_no_active_subscriptions(self, MockCache, mock_reg, mock_check):
        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS:
            MockCS.objects.filter.return_value.values_list.return_value = []

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockCache.set_subscription_id.assert_not_called()
        MockCache.set_features.assert_not_called()
        MockCache.set_limits.assert_not_called()


# ── Lifetime counter seeding ─────────────────────────────────────────────────

class TestWarmupLifetimeCounterSeeding(TestCase):

    def setUp(self):
        super().setUp()
        self._complement = patch(_COMPLEMENT_KEYS, return_value={})
        self._complement.start()
        self.addCleanup(self._complement.stop)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_seeds_lifetime_counter_from_db(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'settings.payment-methods.create'
        limit_obj.max_value = 10
        limit_obj.validation_type = 'lifetime'

        mock_registry.has_counter.return_value = True
        mock_registry.get_count.return_value = 3  # 3 records in DB

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = [
                'settings.payment-methods.create',
            ]
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockStore.set_lifetime.assert_called_once_with(
            str(company), 'settings.payment-methods.create', 3,
        )

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_skips_daily_limits_during_seeding(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        """Daily limits should NOT seed counters — they reset automatically."""
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'api.calls'
        limit_obj.max_value = 10000
        limit_obj.validation_type = 'daily'

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['api.calls']
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockStore.set_lifetime.assert_not_called()

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_skips_window_limits_during_seeding(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        """Window limits should NOT seed counters — they reset with the slot."""
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'assistant.chat'
        limit_obj.max_value = 3
        limit_obj.validation_type = 'window'
        limit_obj.window_hours = 3

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['assistant.chat']
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockStore.set_lifetime.assert_not_called()
        MockCache.set_limits.assert_called_once()
        limits_arg = MockCache.set_limits.call_args[0][1]
        self.assertEqual(limits_arg['assistant.chat']['type'], 'window')
        self.assertEqual(limits_arg['assistant.chat']['window_hours'], 3)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_skips_features_without_registered_counter(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        """Features without a registered counter function are skipped."""
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'reports.export'
        limit_obj.max_value = 50
        limit_obj.validation_type = 'lifetime'

        mock_registry.has_counter.return_value = False

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['reports.export']
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockStore.set_lifetime.assert_not_called()

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_seeds_zero_when_db_count_is_zero(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        company = uuid.uuid4()
        sub_id = uuid.uuid4()

        limit_obj = MagicMock()
        limit_obj.functionality.key = 'settings.payment-methods.create'
        limit_obj.max_value = 10
        limit_obj.validation_type = 'lifetime'

        mock_registry.has_counter.return_value = True
        mock_registry.get_count.return_value = 0

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = [
                'settings.payment-methods.create',
            ]
            MockSL.objects.filter.return_value.select_related.return_value = [limit_obj]

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        MockStore.set_lifetime.assert_called_once_with(
            str(company), 'settings.payment-methods.create', 0,
        )


# ── Plan data reuse across companies ─────────────────────────────────────────

class TestWarmupPlanDataReuse(TestCase):

    def setUp(self):
        super().setUp()
        self._complement = patch(_COMPLEMENT_KEYS, return_value={})
        self._complement.start()
        self.addCleanup(self._complement.stop)

    @patch('core.access.warmup._check_redis', return_value='OK')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup.SubscriptionCache')
    @patch('core.access.warmup.UsageStore')
    @patch('core.access.warmup.usage_registry')
    def test_reuses_features_for_same_plan(
        self, mock_registry, MockStore, MockCache, mock_reg, mock_check,
    ):
        """Two companies on the same plan should share the same feature/limit
        query — SubscriptionFunctionality queried only once per plan."""
        company1 = uuid.uuid4()
        company2 = uuid.uuid4()
        sub_id = uuid.uuid4()

        mock_registry.has_counter.return_value = False

        with patch('platform.features.billing.subscription.subscription.models.CompanySubscription') as MockCS, \
             patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality') as MockSF, \
             patch('platform.features.billing.subscription.subscription_limit.models.SubscriptionLimit') as MockSL:

            MockCS.objects.filter.return_value.values_list.return_value = [
                _active_sub(company1, sub_id),
                _active_sub(company2, sub_id),
            ]
            MockSF.objects.filter.return_value.values_list.return_value = ['orders.create']
            MockSL.objects.filter.return_value.select_related.return_value = []

            from core.access.warmup import warmup_subscription_cache
            warmup_subscription_cache()

        # Features cached for both companies
        self.assertEqual(MockCache.set_features.call_count, 2)
        # But SubscriptionFunctionality only queried once (reused)
        self.assertEqual(MockSF.objects.filter.call_count, 1)


class TestWarmupMinioPolicyLog(TestCase):

    @patch('core.access.warmup._check_erp', return_value='OK')
    @patch('core.access.warmup._check_beat', return_value='OK')
    @patch('core.access.warmup._check_workers', return_value='OK')
    @patch('core.access.warmup._check_ai_runtime', return_value='OK')
    @patch('core.access.warmup._print_banner')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup._check_postgres', return_value='OK')
    @patch('core.access.warmup._check_redis', return_value='ERROR')
    @patch('core.access.warmup._check_minio', return_value='OK')
    def test_does_not_log_minio_public_prefixes_on_startup(
        self, mock_minio, mock_redis, mock_pg, mock_reg, mock_banner,
        mock_ai, mock_workers, mock_beat, mock_erp,
    ):
        from core.access.warmup import warmup_subscription_cache

        with patch(
            'core.storage.profile_bucket.applied_public_policy',
            return_value=('base', ('admin/assets/profile/*', 'client/assets/profile/*')),
        ), patch('core.access.warmup.logger') as mock_logger:
            warmup_subscription_cache()

        info_messages = [c.args[0] for c in mock_logger.info.call_args_list]
        self.assertIn('[startup]   PostgreSQL : %s', info_messages)
        self.assertIn('[startup]   MinIO      : %s', info_messages)
        self.assertIn('[startup]   ERP        : %s', info_messages)
        self.assertNotIn(
            '[startup] MinIO policies | bucket %s, public-read, %d prefixes',
            info_messages,
        )
        prefix_logs = [
            c for c in mock_logger.info.call_args_list
            if c.args and c.args[0] == '[startup]     %s'
        ]
        self.assertEqual(prefix_logs, [])

    @patch('core.access.warmup._check_erp', return_value='OK')
    @patch('core.access.warmup._check_beat', return_value='OK')
    @patch('core.access.warmup._check_workers', return_value='OK')
    @patch('core.access.warmup._check_ai_runtime', return_value='OK')
    @patch('core.access.warmup._print_banner')
    @patch('core.access.warmup._register_counters')
    @patch('core.access.warmup._check_postgres', return_value='OK')
    @patch('core.access.warmup._check_redis', return_value='ERROR')
    @patch('core.access.warmup._check_minio', return_value='ERROR')
    def test_skips_policy_block_when_minio_is_down(
        self, mock_minio, mock_redis, mock_pg, mock_reg, mock_banner,
        mock_ai, mock_workers, mock_beat, mock_erp,
    ):
        from core.access.warmup import warmup_subscription_cache

        with patch('core.access.warmup.logger') as mock_logger:
            warmup_subscription_cache()

        info_messages = [c.args[0] for c in mock_logger.info.call_args_list]
        self.assertIn('[startup]   MinIO      : %s', info_messages)
        self.assertIn('[startup]   ERP        : %s', info_messages)
        self.assertNotIn(
            '[startup] MinIO policies | bucket %s, public-read, %d prefixes',
            info_messages,
        )


class TestWarmupExtendedHealthChecks(TestCase):

    @patch('core.ai.health.probe_inference_health', return_value='ok')
    def test_ai_runtime_ok_when_probe_ok(self, mock_probe):
        from core.access.warmup import _check_ai_runtime

        self.assertEqual(_check_ai_runtime(), 'OK')
        mock_probe.assert_called_once()

    @patch('core.ai.health.probe_inference_health', return_value='down')
    def test_ai_runtime_error_when_probe_down(self, mock_probe):
        from core.access.warmup import _check_ai_runtime

        self.assertEqual(_check_ai_runtime(), 'ERROR')

    @patch('core.tasks.app.app')
    def test_workers_ok_when_ping_returns_workers(self, mock_app):
        from core.access.warmup import _check_workers

        mock_app.control.inspect.return_value.ping.return_value = {
            'celery@host': {'ok': 'pong'},
        }
        self.assertEqual(_check_workers(), 'OK')

    @patch('core.tasks.app.app')
    def test_workers_error_when_ping_empty(self, mock_app):
        from core.access.warmup import _check_workers

        mock_app.control.inspect.return_value.ping.return_value = None
        self.assertEqual(_check_workers(), 'ERROR')

    @patch('redis.from_url')
    def test_beat_ok_when_redbeat_lock_exists(self, mock_from_url):
        from core.access.warmup import _check_beat

        mock_from_url.return_value.exists.return_value = True
        self.assertEqual(_check_beat(), 'OK')

    @patch('redis.from_url')
    def test_beat_error_when_redbeat_lock_missing(self, mock_from_url):
        from core.access.warmup import _check_beat

        mock_from_url.return_value.exists.return_value = False
        self.assertEqual(_check_beat(), 'ERROR')

    @patch('django.conf.settings.NE_PRODUCT_CLIENT_ID', '')
    @patch('django.conf.settings.NE_ECOSYSTEM_BASE_URL', 'http://api.neurana.local:8000')
    @patch('socket.create_connection')
    def test_erp_ok_when_tcp_connects(self, mock_connect):
        from core.access.warmup import _check_erp

        mock_connect.return_value.__enter__.return_value = MagicMock()
        self.assertEqual(_check_erp(), 'OK')
        mock_connect.assert_called_once()
        host, port = mock_connect.call_args[0][0]
        self.assertEqual((host, port), ('api.neurana.local', 8000))

    @patch('django.conf.settings.NE_PRODUCT_CLIENT_ID', '')
    @patch('django.conf.settings.NE_ECOSYSTEM_BASE_URL', 'http://api.neurana.local:8000')
    @patch('socket.create_connection', side_effect=OSError('connection refused'))
    def test_erp_error_when_unreachable(self, mock_connect):
        from core.access.warmup import _check_erp

        self.assertEqual(_check_erp(), 'ERROR')

    @patch('django.conf.settings.NE_PRODUCT_CLIENT_ID', '')
    @patch('django.conf.settings.NE_ECOSYSTEM_BASE_URL', '')
    def test_erp_error_when_base_url_empty(self):
        from core.access.warmup import _check_erp

        self.assertEqual(_check_erp(), 'ERROR')
