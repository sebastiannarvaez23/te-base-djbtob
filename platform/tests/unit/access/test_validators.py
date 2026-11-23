"""
Unit tests for DailyValidator, LifetimeValidator, and UsageCounterRegistry:
  - Validator.matches() for correct validation type
  - get_current_usage delegates to UsageStore
  - track / untrack delegate to UsageStore
  - LimitValidator.validate() compares usage vs max
  - UsageCounterRegistry: register, get_count, has_counter

No Redis or database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch


COMPANY_ID = str(uuid.uuid4())
FEATURE_KEY = 'orders.create'


# ── DailyValidator ───────────────────────────────────────────────────────────

class TestDailyValidatorMatches(TestCase):

    def test_matches_daily(self):
        from core.access.validators.daily import DailyValidator
        v = DailyValidator()
        self.assertTrue(v.matches('daily'))

    def test_does_not_match_lifetime(self):
        from core.access.validators.daily import DailyValidator
        v = DailyValidator()
        self.assertFalse(v.matches('lifetime'))

    def test_does_not_match_unknown(self):
        from core.access.validators.daily import DailyValidator
        v = DailyValidator()
        self.assertFalse(v.matches('monthly'))


class TestDailyValidatorUsage(TestCase):

    @patch('core.access.validators.daily.UsageStore')
    def test_get_current_usage_delegates_to_store(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 42

        v = DailyValidator()
        result = v.get_current_usage(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 42)
        MockStore.get_daily.assert_called_once_with(COMPANY_ID, FEATURE_KEY)

    @patch('core.access.validators.daily.UsageStore')
    def test_track_delegates_to_store(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.increment_daily.return_value = 43

        v = DailyValidator()
        result = v.track(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 43)
        MockStore.increment_daily.assert_called_once_with(COMPANY_ID, FEATURE_KEY)


class TestDailyValidatorValidate(TestCase):

    @patch('core.access.validators.daily.UsageStore')
    def test_under_limit_returns_true(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 50
        v = DailyValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.daily.UsageStore')
    def test_at_limit_returns_false(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 100
        v = DailyValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.daily.UsageStore')
    def test_over_limit_returns_false(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 150
        v = DailyValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.daily.UsageStore')
    def test_zero_usage_returns_true(self, MockStore):
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 0
        v = DailyValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.daily.UsageStore')
    def test_zero_max_at_zero_usage_returns_false(self, MockStore):
        """max_value=0 means no usage allowed at all."""
        from core.access.validators.daily import DailyValidator
        MockStore.get_daily.return_value = 0
        v = DailyValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 0))


class TestDailyValidatorUntrack(TestCase):

    def test_untrack_is_noop(self):
        """Daily validator does not support untrack (returns 0)."""
        from core.access.validators.daily import DailyValidator
        v = DailyValidator()
        result = v.untrack(COMPANY_ID, FEATURE_KEY)
        self.assertEqual(result, 0)


# ── WindowValidator ──────────────────────────────────────────────────────────

class TestWindowValidatorMatches(TestCase):

    def test_matches_window(self):
        from core.access.validators.window import WindowValidator
        v = WindowValidator()
        self.assertTrue(v.matches('window'))

    def test_does_not_match_daily(self):
        from core.access.validators.window import WindowValidator
        v = WindowValidator()
        self.assertFalse(v.matches('daily'))

    def test_does_not_match_lifetime(self):
        from core.access.validators.window import WindowValidator
        v = WindowValidator()
        self.assertFalse(v.matches('lifetime'))


class TestWindowValidatorUsage(TestCase):

    @patch('core.access.validators.window.UsageStore')
    def test_get_current_usage_delegates_to_store(self, MockStore):
        from core.access.validators.window import WindowValidator
        MockStore.get_window.return_value = 2

        v = WindowValidator()
        result = v.get_current_usage(COMPANY_ID, FEATURE_KEY, window_hours=3)

        self.assertEqual(result, 2)
        MockStore.get_window.assert_called_once_with(COMPANY_ID, FEATURE_KEY, 3)

    @patch('core.access.validators.window.UsageStore')
    def test_track_delegates_to_store(self, MockStore):
        from core.access.validators.window import WindowValidator
        MockStore.increment_window.return_value = 3

        v = WindowValidator()
        result = v.track(COMPANY_ID, FEATURE_KEY, window_hours=3)

        self.assertEqual(result, 3)
        MockStore.increment_window.assert_called_once_with(COMPANY_ID, FEATURE_KEY, 3)

    @patch('core.access.validators.window.UsageStore')
    def test_missing_window_hours_does_not_hit_store(self, MockStore):
        from core.access.validators.window import WindowValidator

        v = WindowValidator()
        usage = v.get_current_usage(COMPANY_ID, FEATURE_KEY)

        self.assertGreaterEqual(usage, 2**30)
        MockStore.get_window.assert_not_called()

    @patch('core.access.validators.window.UsageStore')
    def test_quota_resets_at_requires_hours(self, MockStore):
        from core.access.validators.window import WindowValidator
        from datetime import datetime, timezone

        MockStore.window_reset_at.return_value = datetime(1970, 1, 1, 3, 0, tzinfo=timezone.utc)
        v = WindowValidator()
        self.assertIsNone(v.quota_resets_at())
        self.assertEqual(
            v.quota_resets_at(window_hours=3),
            datetime(1970, 1, 1, 3, 0, tzinfo=timezone.utc),
        )
        MockStore.window_reset_at.assert_called_once_with(3)


class TestWindowValidatorValidate(TestCase):

    @patch('core.access.validators.window.UsageStore')
    def test_under_limit_returns_true(self, MockStore):
        from core.access.validators.window import WindowValidator
        MockStore.get_window.return_value = 2
        v = WindowValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 3, window_hours=3))

    @patch('core.access.validators.window.UsageStore')
    def test_at_limit_returns_false(self, MockStore):
        from core.access.validators.window import WindowValidator
        MockStore.get_window.return_value = 3
        v = WindowValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 3, window_hours=3))

    @patch('core.access.validators.window.UsageStore')
    def test_over_limit_returns_false(self, MockStore):
        from core.access.validators.window import WindowValidator
        MockStore.get_window.return_value = 4
        v = WindowValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 3, window_hours=3))


class TestWindowValidatorUntrack(TestCase):

    def test_untrack_is_noop(self):
        from core.access.validators.window import WindowValidator
        v = WindowValidator()
        result = v.untrack(COMPANY_ID, FEATURE_KEY, window_hours=3)
        self.assertEqual(result, 0)


# ── LifetimeValidator ────────────────────────────────────────────────────────

class TestLifetimeValidatorMatches(TestCase):

    def test_matches_lifetime(self):
        from core.access.validators.lifetime import LifetimeValidator
        v = LifetimeValidator()
        self.assertTrue(v.matches('lifetime'))

    def test_does_not_match_daily(self):
        from core.access.validators.lifetime import LifetimeValidator
        v = LifetimeValidator()
        self.assertFalse(v.matches('daily'))

    def test_does_not_match_unknown(self):
        from core.access.validators.lifetime import LifetimeValidator
        v = LifetimeValidator()
        self.assertFalse(v.matches('monthly'))


class TestLifetimeValidatorUsage(TestCase):

    @patch('core.access.validators.lifetime.UsageStore')
    def test_get_current_usage_delegates_to_store(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 500

        v = LifetimeValidator()
        result = v.get_current_usage(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 500)
        MockStore.get_lifetime.assert_called_once_with(COMPANY_ID, FEATURE_KEY)

    @patch('core.access.validators.lifetime.UsageStore')
    def test_track_delegates_to_store(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.increment_lifetime.return_value = 501

        v = LifetimeValidator()
        result = v.track(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 501)
        MockStore.increment_lifetime.assert_called_once_with(COMPANY_ID, FEATURE_KEY)

    @patch('core.access.validators.lifetime.UsageStore')
    def test_untrack_delegates_to_store(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.decrement_lifetime.return_value = 499

        v = LifetimeValidator()
        result = v.untrack(COMPANY_ID, FEATURE_KEY)

        self.assertEqual(result, 499)
        MockStore.decrement_lifetime.assert_called_once_with(COMPANY_ID, FEATURE_KEY)


class TestLifetimeValidatorValidate(TestCase):

    @patch('core.access.validators.lifetime.UsageStore')
    def test_under_limit_returns_true(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 50
        v = LifetimeValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.lifetime.UsageStore')
    def test_at_limit_returns_false(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 100
        v = LifetimeValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.lifetime.UsageStore')
    def test_over_limit_returns_false(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 150
        v = LifetimeValidator()

        self.assertFalse(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.lifetime.UsageStore')
    def test_zero_usage_returns_true(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 0
        v = LifetimeValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 100))

    @patch('core.access.validators.lifetime.UsageStore')
    def test_one_below_limit_returns_true(self, MockStore):
        from core.access.validators.lifetime import LifetimeValidator
        MockStore.get_lifetime.return_value = 99
        v = LifetimeValidator()

        self.assertTrue(v.validate(COMPANY_ID, FEATURE_KEY, 100))


# ── UsageCounterRegistry ────────────────────────────────────────────────────

class TestUsageCounterRegistry(TestCase):

    def test_register_and_get_count(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()

        counter_fn = MagicMock(return_value=42)
        registry.register('orders.create', counter_fn)

        result = registry.get_count('orders.create', COMPANY_ID)

        self.assertEqual(result, 42)
        counter_fn.assert_called_once_with(COMPANY_ID)

    def test_has_counter_true(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()
        registry.register('orders.create', lambda cid: 0)

        self.assertTrue(registry.has_counter('orders.create'))

    def test_has_counter_false(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()

        self.assertFalse(registry.has_counter('unknown.feature'))

    def test_get_count_returns_none_for_unregistered(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()

        result = registry.get_count('unknown.feature', COMPANY_ID)

        self.assertIsNone(result)

    def test_get_count_handles_exception(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()
        registry.register('orders.create', MagicMock(side_effect=Exception('DB error')))

        result = registry.get_count('orders.create', COMPANY_ID)

        self.assertIsNone(result)

    def test_registered_keys(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()
        registry.register('orders.create', lambda cid: 0)
        registry.register('api.calls', lambda cid: 0)

        keys = registry.registered_keys

        self.assertIn('orders.create', keys)
        self.assertIn('api.calls', keys)
        self.assertEqual(len(keys), 2)

    def test_register_overwrites_existing(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()

        fn1 = MagicMock(return_value=10)
        fn2 = MagicMock(return_value=20)
        registry.register('orders.create', fn1)
        registry.register('orders.create', fn2)

        result = registry.get_count('orders.create', COMPANY_ID)

        self.assertEqual(result, 20)
        fn1.assert_not_called()
        fn2.assert_called_once()

    def test_empty_registry(self):
        from core.access.registry import UsageCounterRegistry
        registry = UsageCounterRegistry()

        self.assertEqual(registry.registered_keys, [])
        self.assertFalse(registry.has_counter('anything'))


# ── track_usage / untrack_usage decorators ───────────────────────────────────

class TestTrackUsageDecorator(TestCase):

    @patch('core.access.decorators.AccessChecker')
    def test_track_usage_increments_on_2xx(self, MockChecker):
        from core.access.decorators import track_usage

        company = MagicMock()
        company.id = uuid.uuid4()

        request = MagicMock()
        request.tenant = company

        view_instance = MagicMock()

        @track_usage('orders.create')
        def create(self, request):
            response = MagicMock()
            response.status_code = 201
            return response

        response = create(view_instance, request)

        self.assertEqual(response.status_code, 201)
        MockChecker.track_usage.assert_called_once_with(company, 'orders.create')

    @patch('core.access.decorators.AccessChecker')
    def test_track_usage_skips_on_4xx(self, MockChecker):
        from core.access.decorators import track_usage

        request = MagicMock()
        request.tenant = MagicMock()

        view_instance = MagicMock()

        @track_usage('orders.create')
        def create(self, request):
            response = MagicMock()
            response.status_code = 400
            return response

        create(view_instance, request)

        MockChecker.track_usage.assert_not_called()

    @patch('core.access.decorators.AccessChecker')
    def test_track_usage_skips_on_5xx(self, MockChecker):
        from core.access.decorators import track_usage

        request = MagicMock()
        request.tenant = MagicMock()
        view_instance = MagicMock()

        @track_usage('orders.create')
        def create(self, request):
            response = MagicMock()
            response.status_code = 500
            return response

        create(view_instance, request)

        MockChecker.track_usage.assert_not_called()

    @patch('core.access.decorators.AccessChecker')
    def test_track_usage_skips_without_tenant(self, MockChecker):
        from core.access.decorators import track_usage

        request = MagicMock()
        request.tenant = None
        view_instance = MagicMock()

        @track_usage('orders.create')
        def create(self, request):
            response = MagicMock()
            response.status_code = 201
            return response

        create(view_instance, request)

        MockChecker.track_usage.assert_not_called()

    @patch('core.access.decorators.AccessChecker')
    def test_track_usage_swallows_exceptions(self, MockChecker):
        """track_usage should not break the response even if tracking fails."""
        from core.access.decorators import track_usage

        MockChecker.track_usage.side_effect = Exception('Redis down')
        request = MagicMock()
        request.tenant = MagicMock()
        view_instance = MagicMock()

        @track_usage('orders.create')
        def create(self, request):
            response = MagicMock()
            response.status_code = 201
            return response

        # Should not raise
        response = create(view_instance, request)
        self.assertEqual(response.status_code, 201)


class TestUntrackUsageDecorator(TestCase):

    @patch('core.access.decorators.AccessChecker')
    def test_untrack_usage_decrements_on_2xx(self, MockChecker):
        from core.access.decorators import untrack_usage

        company = MagicMock()
        request = MagicMock()
        request.tenant = company
        view_instance = MagicMock()

        @untrack_usage('orders.create')
        def destroy(self, request):
            response = MagicMock()
            response.status_code = 204
            return response

        destroy(view_instance, request)

        MockChecker.untrack_usage.assert_called_once_with(company, 'orders.create')

    @patch('core.access.decorators.AccessChecker')
    def test_untrack_usage_skips_on_4xx(self, MockChecker):
        from core.access.decorators import untrack_usage

        request = MagicMock()
        request.tenant = MagicMock()
        view_instance = MagicMock()

        @untrack_usage('orders.create')
        def destroy(self, request):
            response = MagicMock()
            response.status_code = 404
            return response

        destroy(view_instance, request)

        MockChecker.untrack_usage.assert_not_called()

    @patch('core.access.decorators.AccessChecker')
    def test_untrack_usage_skips_without_tenant(self, MockChecker):
        from core.access.decorators import untrack_usage

        request = MagicMock()
        request.tenant = None
        view_instance = MagicMock()

        @untrack_usage('orders.create')
        def destroy(self, request):
            response = MagicMock()
            response.status_code = 204
            return response

        destroy(view_instance, request)

        MockChecker.untrack_usage.assert_not_called()

    @patch('core.access.decorators.AccessChecker')
    def test_untrack_usage_swallows_exceptions(self, MockChecker):
        from core.access.decorators import untrack_usage

        MockChecker.untrack_usage.side_effect = Exception('Redis down')
        request = MagicMock()
        request.tenant = MagicMock()
        view_instance = MagicMock()

        @untrack_usage('orders.create')
        def destroy(self, request):
            response = MagicMock()
            response.status_code = 204
            return response

        # Should not raise
        response = destroy(view_instance, request)
        self.assertEqual(response.status_code, 204)
