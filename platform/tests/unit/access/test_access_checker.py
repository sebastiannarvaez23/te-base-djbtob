"""
Unit tests for AccessChecker, HasSubscriptionAccess permission,
and usage tracking (track/untrack):
  - Full 4-step verification flow
  - Cache miss → DB fallback
  - Daily and lifetime validators
  - Track / untrack usage
  - HasSubscriptionAccess permission class
  - Unknown validation type (fail-open)

No database or Redis required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from core.access.checker import AccessChecker
from core.access.result import AccessResult
from core.errors.codes import AppErrorCode
from core.errors.exceptions import SubscriptionException


# ── Helper ─────────────────────────────────────────────────────────────────────

def _company():
    company = MagicMock()
    company.id = uuid.uuid4()
    return company


# ── AccessChecker.check_feature — full flow ──────────────────────────────────

class TestAccessCheckerCheckFeature(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_step1_no_subscription_in_cache_or_db(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = None

        with patch.object(AccessChecker, '_load_subscription_id', return_value=None):
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_NO_ACTIVE)

    @patch('core.access.checker.SubscriptionCache')
    def test_step1_subscription_found_in_cache(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step1_subscription_loaded_from_db_on_cache_miss(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = None

        with patch.object(AccessChecker, '_load_subscription_id', return_value='sub-db') as mock_load:
            MockCache.get_features.return_value = {'orders.create'}
            MockCache.get_limits.return_value = {}

            result = AccessChecker.check_feature(company, 'orders.create')

        mock_load.assert_called_once()
        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step1_negative_cache_short_circuits_without_db(self, MockCache):
        """Caché negativa ('' = se sabe que no hay plan): debe cortar con
        SUB_NO_ACTIVE SIN volver a consultar la BD, y no continuar hacia
        SUB_FEATURE_DENIED con un subscription_id vacío."""
        company = _company()
        MockCache.get_subscription_id.return_value = ''  # negativa cacheada

        with patch.object(AccessChecker, '_load_subscription_id') as mock_load:
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_NO_ACTIVE)
        mock_load.assert_not_called()

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_step2_feature_not_in_plan(self, MockCache, _diagnose):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.view'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'reports.export')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)

    @patch('core.access.checker.SubscriptionCache')
    def test_step2_features_loaded_from_db_on_cache_miss(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = None  # cache miss

        with patch.object(AccessChecker, '_load_features', return_value={'orders.create'}):
            MockCache.get_limits.return_value = {}
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step3_no_limit_means_unlimited(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step3_limits_loaded_from_db_on_cache_miss(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = None  # cache miss

        with patch.object(AccessChecker, '_load_limits', return_value={}):
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_lifetime_under_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 50
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_lifetime_at_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 100
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_daily_under_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 5000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 2000
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_daily_at_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 5000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 5000
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_window_under_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'assistant.chat'}
        MockCache.get_limits.return_value = {
            'assistant.chat': {'max': 3, 'type': 'window', 'window_hours': 3},
        }

        with patch('core.access.validators.window.UsageStore') as MockStore:
            MockStore.get_window.return_value = 2
            result = AccessChecker.check_feature(company, 'assistant.chat')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_window_at_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'assistant.chat'}
        MockCache.get_limits.return_value = {
            'assistant.chat': {'max': 3, 'type': 'window', 'window_hours': 3},
        }

        with patch('core.access.validators.window.UsageStore') as MockStore:
            MockStore.get_window.return_value = 3
            result = AccessChecker.check_feature(company, 'assistant.chat')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)
        self.assertIn('resets_at', result.context)
        self.assertEqual(result.context['validation_type'], 'window')

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_window_at_limit_skipped_when_check_quota_false(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'assistant.chat'}
        MockCache.get_limits.return_value = {
            'assistant.chat': {'max': 3, 'type': 'window', 'window_hours': 3},
        }

        result = AccessChecker.check_feature(
            company, 'assistant.chat', check_quota=False,
        )

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_step4_window_missing_hours_denies(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'assistant.chat'}
        MockCache.get_limits.return_value = {
            'assistant.chat': {'max': 3, 'type': 'window'},
        }

        result = AccessChecker.check_feature(company, 'assistant.chat')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_unknown_validation_type_allows_access_fail_open(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'unknown_type'},
        }

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_quota_exceeded_detail_includes_usage_info(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-abc'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 50, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 75
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertIn('orders.create', result.detail)
        self.assertIn('50', result.detail)
        self.assertEqual(result.context['max_value'], 50)
        self.assertEqual(result.context['current_usage'], 75)
        self.assertEqual(result.context['validation_type'], 'lifetime')


# ── AccessChecker.track_usage ────────────────────────────────────────────────

class TestAccessCheckerTrackUsage(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_calls_lifetime_validator(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.increment_lifetime.return_value = 51
            AccessChecker.track_usage(company, 'orders.create')
            MockStore.increment_lifetime.assert_called_once()

    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_calls_daily_validator(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 10000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.increment_daily.return_value = 5001
            AccessChecker.track_usage(company, 'api.calls')
            MockStore.increment_daily.assert_called_once()

    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_calls_window_validator(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {
            'assistant.chat': {'max': 3, 'type': 'window', 'window_hours': 3},
        }

        with patch('core.access.validators.window.UsageStore') as MockStore:
            MockStore.increment_window.return_value = 1
            AccessChecker.track_usage(company, 'assistant.chat')
            MockStore.increment_window.assert_called_once()

    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_noop_when_no_limit(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {}

        # Should not raise — just silently return
        AccessChecker.track_usage(company, 'orders.create')

    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_noop_when_no_subscription(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = None
        MockCache.get_subscription_id.return_value = None

        with patch.object(AccessChecker, '_load_subscription_id', return_value=None):
            AccessChecker.track_usage(company, 'orders.create')

    @patch('core.access.checker.logger')
    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_logs_breach_when_over_limit(self, MockCache, mock_logger):
        """Si el INCR atómico deja el contador por encima del tope (carrera en
        el gate), se emite un warning QUOTA_BREACH sin revertir el contador."""
        company = _company()
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.increment_lifetime.return_value = 101  # sobrepasó el tope
            AccessChecker.track_usage(company, 'orders.create')

        mock_logger.warning.assert_called_once()
        self.assertIn('QUOTA_BREACH', mock_logger.warning.call_args[0][0])

    @patch('core.access.checker.logger')
    @patch('core.access.checker.SubscriptionCache')
    def test_track_usage_no_breach_log_within_limit(self, MockCache, mock_logger):
        company = _company()
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.increment_lifetime.return_value = 50
            AccessChecker.track_usage(company, 'orders.create')

        mock_logger.warning.assert_not_called()


# ── AccessChecker.untrack_usage ──────────────────────────────────────────────

class TestAccessCheckerUntrackUsage(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_untrack_usage_calls_lifetime_validator(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.decrement_lifetime.return_value = 49
            AccessChecker.untrack_usage(company, 'orders.create')
            MockStore.decrement_lifetime.assert_called_once()

    @patch('core.access.checker.SubscriptionCache')
    def test_untrack_usage_noop_when_no_limit(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = {}

        AccessChecker.untrack_usage(company, 'orders.create')

    @patch('core.access.checker.SubscriptionCache')
    def test_untrack_usage_noop_when_no_subscription(self, MockCache):
        company = _company()
        MockCache.get_limits.return_value = None
        MockCache.get_subscription_id.return_value = None

        with patch.object(AccessChecker, '_load_subscription_id', return_value=None):
            AccessChecker.untrack_usage(company, 'orders.create')


# ── AccessResult constructors ────────────────────────────────────────────────

class TestAccessResult(TestCase):

    def test_allowed_result(self):
        r = AccessResult.allowed()
        self.assertTrue(r.is_allowed)
        self.assertIsNone(r.error_code)
        self.assertEqual(r.detail, '')

    def test_no_subscription_result(self):
        r = AccessResult.no_subscription()
        self.assertFalse(r.is_allowed)
        self.assertEqual(r.error_code, AppErrorCode.SUB_NO_ACTIVE)
        self.assertIn('subscription', r.detail.lower())

    def test_feature_denied_result(self):
        r = AccessResult.feature_denied('reports.export')
        self.assertFalse(r.is_allowed)
        self.assertEqual(r.error_code, AppErrorCode.SUB_FEATURE_DENIED)
        self.assertIn('reports.export', r.detail)
        self.assertEqual(r.context['feature_key'], 'reports.export')

    def test_quota_exceeded_result(self):
        r = AccessResult.quota_exceeded('orders.create', 100, 150, 'lifetime')
        self.assertFalse(r.is_allowed)
        self.assertEqual(r.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)
        self.assertEqual(r.context['max_value'], 100)
        self.assertEqual(r.context['current_usage'], 150)
        self.assertEqual(r.context['validation_type'], 'lifetime')
        self.assertIn('150/100', r.detail)
        self.assertNotIn('resets_at', r.context)

    def test_quota_exceeded_includes_resets_at(self):
        from datetime import datetime, timezone
        resets = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)
        r = AccessResult.quota_exceeded(
            'assistant.chat', 3, 3, 'window', resets_at=resets,
        )
        self.assertEqual(r.context['resets_at'], '2026-08-24T03:00:00+00:00')
        self.assertEqual(r.context['validation_type'], 'window')

    def test_quota_exceeded_daily(self):
        r = AccessResult.quota_exceeded('api.calls', 5000, 5000, 'daily')
        self.assertEqual(r.context['validation_type'], 'daily')
        self.assertIn('daily', r.detail)


# ── HasSubscriptionAccess permission ─────────────────────────────────────────

class TestHasSubscriptionAccessPermission(TestCase):

    def setUp(self):
        from core.permissions import HasSubscriptionAccess
        self.permission = HasSubscriptionAccess()
        # Esta suite cubre suscripción/cupos. El gate de rol tiene pruebas
        # dedicadas en core/tests/unit/access/test_access_invalidation.py.
        self.permission._assert_role_allows = MagicMock()

    def test_no_subscription_functionality_attr_passes(self):
        """Views without subscription_functionality pass without check."""
        request = MagicMock()
        view = MagicMock(spec=[])  # no subscription_functionality attr

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)

    def test_no_tenant_passes(self):
        """Without a tenant (admin portal), permission passes."""
        request = MagicMock()
        request.tenant = None
        request.user.company = None
        request.user.company_id = None
        view = MagicMock()
        view.subscription_functionality = 'orders.create'
        view.get_subscription_functionality = None
        del view.get_subscription_functionality

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)

    @patch('core.permissions.AccessChecker')
    def test_allowed_feature_passes(self, MockChecker):
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = 'orders.create'
        # Remove get_subscription_functionality to avoid method resolution
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        MockChecker.check_feature.assert_called_once_with(
            request.tenant, 'orders.create', check_quota=True,
        )

    @patch('core.permissions.AccessChecker')
    def test_denied_feature_raises_subscription_exception(self, MockChecker):
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = 'orders.create'
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.feature_denied('orders.create')

        with self.assertRaises(SubscriptionException) as ctx:
            self.permission.has_permission(request, view)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_FEATURE_DENIED)

    @patch('core.permissions.AccessChecker')
    def test_no_subscription_raises_subscription_exception(self, MockChecker):
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = 'orders.create'
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.no_subscription()

        with self.assertRaises(SubscriptionException) as ctx:
            self.permission.has_permission(request, view)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_NO_ACTIVE)

    @patch('core.permissions.AccessChecker')
    def test_quota_exceeded_raises_subscription_exception(self, MockChecker):
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = 'orders.create'
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.quota_exceeded(
            'orders.create', 100, 100, 'lifetime',
        )

        with self.assertRaises(SubscriptionException) as ctx:
            self.permission.has_permission(request, view)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.permissions.AccessChecker')
    def test_dict_functionality_resolves_by_action(self, MockChecker):
        """When subscription_functionality is a dict, the key is resolved
        from view.action (ViewSet) or request.method (APIView)."""
        request = MagicMock()
        request.tenant = _company()
        request.method = 'POST'
        view = MagicMock()
        view.subscription_functionality = {
            'list': 'orders.view',
            'create': 'orders.create',
        }
        view.action = 'create'
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        MockChecker.check_feature.assert_called_once_with(
            request.tenant, 'orders.create', check_quota=True,
        )

    @patch('core.permissions.AccessChecker')
    def test_dict_functionality_no_matching_action_passes(self, MockChecker):
        """If the current action is not in the dict, feature_key is None → pass."""
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = {
            'list': 'orders.view',
        }
        view.action = 'retrieve'
        del view.get_subscription_functionality

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        MockChecker.check_feature.assert_not_called()

    @patch('core.permissions.AccessChecker')
    def test_dynamic_method_resolution(self, MockChecker):
        """Views with get_subscription_functionality() method use it."""
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.get_subscription_functionality = MagicMock(return_value='dynamic.key')
        # Remove the static attr so the method takes precedence
        del view.subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        view.get_subscription_functionality.assert_called_once_with(request)
        MockChecker.check_feature.assert_called_once_with(
            request.tenant, 'dynamic.key', check_quota=True,
        )

    @patch('core.permissions.AccessChecker')
    def test_list_of_keys_all_must_pass(self, MockChecker):
        """When feature_key is a list, ALL keys must be allowed."""
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.get_subscription_functionality = MagicMock(
            return_value=['orders.create', 'orders.view']
        )
        del view.subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        self.assertEqual(MockChecker.check_feature.call_count, 2)

    @patch('core.permissions.AccessChecker')
    def test_skips_quota_when_view_disables_it(self, MockChecker):
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.subscription_functionality = 'assistant.chat'
        view.subscription_check_quota = False
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        MockChecker.check_feature.assert_called_once_with(
            request.tenant, 'assistant.chat', check_quota=False,
        )

    @patch('core.permissions.AccessChecker')
    def test_prefers_jwt_company_over_hostname_tenant(self, MockChecker):
        jwt_company = _company()
        public_tenant = _company()
        request = MagicMock()
        request.tenant = public_tenant
        request.user.company = jwt_company
        request.user.company_id = jwt_company.id
        view = MagicMock()
        view.subscription_functionality = 'settings.subscription.view'
        del view.get_subscription_functionality

        MockChecker.check_feature.return_value = AccessResult.allowed()

        result = self.permission.has_permission(request, view)

        self.assertTrue(result)
        MockChecker.check_feature.assert_called_once_with(
            jwt_company, 'settings.subscription.view', check_quota=True,
        )

    @patch('core.permissions.AccessChecker')
    def test_list_of_keys_one_denied_raises(self, MockChecker):
        """If any key in a list is denied, the whole check fails."""
        request = MagicMock()
        request.tenant = _company()
        view = MagicMock()
        view.get_subscription_functionality = MagicMock(
            return_value=['orders.create', 'orders.view']
        )
        del view.subscription_functionality

        MockChecker.check_feature.side_effect = [
            AccessResult.allowed(),
            AccessResult.feature_denied('orders.view'),
        ]

        with self.assertRaises(SubscriptionException):
            self.permission.has_permission(request, view)
