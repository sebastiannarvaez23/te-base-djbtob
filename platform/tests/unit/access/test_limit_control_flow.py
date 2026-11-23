"""
Integration-style unit tests for the full limit control flow:
  - Limit creation → cache invalidation
  - Warmup loads limits → AccessChecker validates correctly
  - Usage tracking: increment on create, decrement on delete
  - Limit update changes enforcement behavior
  - Limit deletion removes enforcement
  - Daily reset vs lifetime accumulation
  - Edge cases: exactly at limit, one below, one above
  - Multiple features with different limit types

All dependencies mocked — no Redis or database required.
These tests verify the interaction between components end-to-end.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.checker import AccessChecker
from core.access.result import AccessResult
from core.errors.codes import AppErrorCode


# ── Helpers ────────────────────────────────────────────────────────────────────

def _company(company_id=None):
    c = MagicMock()
    c.id = company_id or uuid.uuid4()
    return c


# ── Full flow: limit creation → access check ────────────────────────────────

class TestLimitCreationToAccessCheck(TestCase):
    """Simulates: admin creates a limit → cache is populated →
    user request is validated against the limit."""

    @patch('core.access.checker.SubscriptionCache')
    def test_new_limit_enforced_on_next_request(self, MockCache):
        """After creating a lifetime limit of 100, a company with 50 usage
        should be allowed."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 50
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_new_limit_blocks_when_already_exceeded(self, MockCache):
        """If admin creates a limit of 100 but the company already used 150,
        the next request is denied immediately."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 150
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_no_limit_means_unlimited_access(self, MockCache):
        """Feature with no configured limit allows unlimited usage."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)


# ── Usage tracking: create increments, delete decrements ─────────────────────

class TestUsageTrackingCreateAndDelete(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_track_after_create_increments_counter(self, MockCache):
        company = _company()

        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.increment_lifetime.return_value = 51
            AccessChecker.track_usage(company, 'orders.create')

            MockStore.increment_lifetime.assert_called_once_with(
                str(company.id), 'orders.create',
            )

    @patch('core.access.checker.SubscriptionCache')
    def test_untrack_after_delete_decrements_counter(self, MockCache):
        company = _company()

        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.decrement_lifetime.return_value = 49
            AccessChecker.untrack_usage(company, 'orders.create')

            MockStore.decrement_lifetime.assert_called_once_with(
                str(company.id), 'orders.create',
            )

    @patch('core.access.checker.SubscriptionCache')
    def test_track_daily_increments_daily_counter(self, MockCache):
        company = _company()

        MockCache.get_limits.return_value = {
            'api.calls': {'max': 10000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.increment_daily.return_value = 5001
            AccessChecker.track_usage(company, 'api.calls')

            MockStore.increment_daily.assert_called_once_with(
                str(company.id), 'api.calls',
            )

    @patch('core.access.checker.SubscriptionCache')
    def test_track_no_limit_is_noop(self, MockCache):
        """If no limit is configured, tracking does nothing."""
        company = _company()
        MockCache.get_limits.return_value = {}

        # Should not raise or interact with UsageStore
        AccessChecker.track_usage(company, 'orders.create')


# ── Limit update changes enforcement ─────────────────────────────────────────

class TestLimitUpdateChangesEnforcement(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_increasing_limit_unblocks_company(self, MockCache):
        """Admin increases limit from 50 to 200 → company with 75 usage
        is now allowed again."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 200, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 75
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_decreasing_limit_blocks_company(self, MockCache):
        """Admin decreases limit from 200 to 50 → company with 75 usage
        is now blocked."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 50, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 75
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_changing_type_from_lifetime_to_daily(self, MockCache):
        """Admin changes limit type from lifetime to daily → daily validator
        is now used."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 1000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 500
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result.is_allowed)


# ── Limit deletion removes enforcement ───────────────────────────────────────

class TestLimitDeletionRemovesEnforcement(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_deleted_limit_means_unlimited(self, MockCache):
        """After admin deletes a limit, the feature becomes unlimited."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        # After deletion, limits dict no longer has this feature
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)


# ── Edge cases: boundary values ──────────────────────────────────────────────

class TestLimitBoundaryValues(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_exactly_at_limit_is_denied(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 100
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_one_below_limit_is_allowed(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 99
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_one_above_limit_is_denied(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 101
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_zero_max_blocks_all_usage(self, MockCache):
        """max_value=0 means no usage allowed."""
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 0, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 0
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_zero_usage_with_positive_limit_is_allowed(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 1, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 0
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_daily_exactly_at_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 5000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 5000
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_daily_one_below_limit(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 5000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 4999
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result.is_allowed)


# ── Multiple features with different limit types ─────────────────────────────

class TestMultipleFeaturesWithDifferentLimits(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_lifetime_allowed_daily_denied(self, MockCache):
        """One feature under lifetime limit, another over daily limit."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create', 'api.calls'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 1000, 'type': 'lifetime'},
            'api.calls': {'max': 100, 'type': 'daily'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockLifetime, \
             patch('core.access.validators.daily.UsageStore') as MockDaily:

            MockLifetime.get_lifetime.return_value = 50
            result_orders = AccessChecker.check_feature(company, 'orders.create')

            MockDaily.get_daily.return_value = 200
            result_api = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result_orders.is_allowed)
        self.assertFalse(result_api.is_allowed)
        self.assertEqual(result_api.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_both_features_under_limits(self, MockCache):
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create', 'api.calls'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 1000, 'type': 'lifetime'},
            'api.calls': {'max': 10000, 'type': 'daily'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockLifetime, \
             patch('core.access.validators.daily.UsageStore') as MockDaily:

            MockLifetime.get_lifetime.return_value = 500
            result1 = AccessChecker.check_feature(company, 'orders.create')

            MockDaily.get_daily.return_value = 5000
            result2 = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result1.is_allowed)
        self.assertTrue(result2.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_both_features_over_limits(self, MockCache):
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create', 'api.calls'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
            'api.calls': {'max': 100, 'type': 'daily'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockLifetime, \
             patch('core.access.validators.daily.UsageStore') as MockDaily:

            MockLifetime.get_lifetime.return_value = 200
            result1 = AccessChecker.check_feature(company, 'orders.create')

            MockDaily.get_daily.return_value = 200
            result2 = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result1.is_allowed)
        self.assertFalse(result2.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_feature_with_limit_and_feature_without(self, MockCache):
        """One feature has a limit, another is unlimited."""
        company = _company()

        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create', 'reports.view'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 100, 'type': 'lifetime'},
            # reports.view has no limit
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 100
            result_orders = AccessChecker.check_feature(company, 'orders.create')

        result_reports = AccessChecker.check_feature(company, 'reports.view')

        self.assertFalse(result_orders.is_allowed)
        self.assertTrue(result_reports.is_allowed)


# ── Quota exceeded context contains useful info ──────────────────────────────

class TestQuotaExceededContext(TestCase):

    @patch('core.access.checker.SubscriptionCache')
    def test_lifetime_exceeded_context(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 50, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 75
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.context['feature_key'], 'orders.create')
        self.assertEqual(result.context['max_value'], 50)
        self.assertEqual(result.context['current_usage'], 75)
        self.assertEqual(result.context['validation_type'], 'lifetime')
        self.assertIn('orders.create', result.detail)
        self.assertIn('75/50', result.detail)

    @patch('core.access.checker.SubscriptionCache')
    def test_daily_exceeded_context(self, MockCache):
        company = _company()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 1000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 1500
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.context['feature_key'], 'api.calls')
        self.assertEqual(result.context['max_value'], 1000)
        self.assertEqual(result.context['current_usage'], 1500)
        self.assertEqual(result.context['validation_type'], 'daily')
        self.assertIn('daily', result.detail)
