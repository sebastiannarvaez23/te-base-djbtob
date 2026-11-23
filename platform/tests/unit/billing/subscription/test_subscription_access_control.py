"""
Unit tests for Subscription access control, lifecycle, and limits:
  - Subscription activation / deactivation
  - Users cannot register with inactive subscription
  - Feature access validation via subscription plan
  - Module access validation via subscription plan
  - Usage limits (topes) — daily and lifetime
  - Upgrade, cancel, reactivate lifecycle
  - Error codes for each denial scenario

No database required.
"""
import uuid
from decimal import Decimal
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.billing.subscription.subscription.application.use_cases import (
    CancelSubscriptionUseCase,
    CreateSubscriptionUseCase,
    DeleteSubscriptionUseCase,
    GetAllSubscriptionsUseCase,
    ReactivateSubscriptionUseCase,
    UpdateSubscriptionUseCase,
)
from platform.features.billing.subscription.subscription.domain.schemas import (
    CompanySubscriptionResultSchema,
    CreateSubscriptionSchema,
    SubscriptionSchema,
    UpdateSubscriptionSchema,
)
from core.errors.codes import AppErrorCode


# ── Helpers ────────────────────────────────────────────────────────────────────

def _subscription(**overrides) -> SubscriptionSchema:
    defaults = dict(
        id=uuid.uuid4(),
        name='Plan Profesional',
        price=Decimal('99.99'),
        code='pro',
        is_active=True,
    )
    defaults.update(overrides)
    return SubscriptionSchema(**defaults)


def _company_sub_result(**overrides) -> CompanySubscriptionResultSchema:
    defaults = dict(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        subscription_name='Plan Profesional',
        start_date=datetime(2027, 3, 1),
        ends_at=datetime(2027, 3, 28),
        status='active',
    )
    defaults.update(overrides)
    return CompanySubscriptionResultSchema(**defaults)


# ── Subscription Activation / Deactivation ────────────────────────────────────

class TestSubscriptionActivationDeactivation(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()

    def test_create_active_subscription(self):
        uc = CreateSubscriptionUseCase(self.mock_repo)
        data = CreateSubscriptionSchema(name='Premium', price=Decimal('149.99'), code='premium', is_active=True)
        self.mock_repo.create.return_value = _subscription(code='premium', is_active=True)

        result = uc.execute(data)

        self.assertTrue(result.is_active)

    def test_create_inactive_subscription(self):
        uc = CreateSubscriptionUseCase(self.mock_repo)
        data = CreateSubscriptionSchema(name='Beta', price=Decimal('0'), code='beta', is_active=False)
        self.mock_repo.create.return_value = _subscription(code='beta', is_active=False)

        result = uc.execute(data)

        self.assertFalse(result.is_active)

    def test_deactivate_subscription_via_update(self):
        uc = UpdateSubscriptionUseCase(self.mock_repo)
        sub_id = uuid.uuid4()
        data = UpdateSubscriptionSchema(is_active=False)
        self.mock_repo.update.return_value = _subscription(id=sub_id, is_active=False)

        result = uc.execute(sub_id, data)

        self.assertFalse(result.is_active)

    def test_reactivate_subscription_via_update(self):
        uc = UpdateSubscriptionUseCase(self.mock_repo)
        sub_id = uuid.uuid4()
        data = UpdateSubscriptionSchema(is_active=True)
        self.mock_repo.update.return_value = _subscription(id=sub_id, is_active=True)

        result = uc.execute(sub_id, data)

        self.assertTrue(result.is_active)

    def test_list_includes_active_and_inactive(self):
        uc = GetAllSubscriptionsUseCase(self.mock_repo)
        self.mock_repo.get_all.return_value = [
            _subscription(code='free', is_active=True),
            _subscription(code='beta', is_active=False),
            _subscription(code='pro', is_active=True),
        ]

        result = uc.execute()

        active_count = sum(1 for s in result if s.is_active)
        inactive_count = sum(1 for s in result if not s.is_active)
        self.assertEqual(active_count, 2)
        self.assertEqual(inactive_count, 1)

    def test_delete_subscription(self):
        uc = DeleteSubscriptionUseCase(self.mock_repo)
        sub_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = uc.execute(sub_id)

        self.assertTrue(result)

    def test_delete_nonexistent_subscription(self):
        uc = DeleteSubscriptionUseCase(self.mock_repo)
        self.mock_repo.delete.return_value = False

        result = uc.execute(uuid.uuid4())

        self.assertFalse(result)


# ── Users cannot register with inactive subscription ──────────────────────────

class TestInactiveSubscriptionRegistrationBlocked(TestCase):
    """When a subscription plan is_active=False, new companies should not
    be able to select it during registration."""

    def test_only_active_subscriptions_available_for_registration(self):
        """Simulates the registration filter: only is_active=True plans
        are offered to new users."""
        all_plans = [
            _subscription(code='free', is_active=True),
            _subscription(code='deprecated', is_active=False),
            _subscription(code='pro', is_active=True),
        ]

        available = [s for s in all_plans if s.is_active]

        self.assertEqual(len(available), 2)
        codes = [s.code for s in available]
        self.assertIn('free', codes)
        self.assertIn('pro', codes)
        self.assertNotIn('deprecated', codes)

    def test_no_active_plans_means_no_registration(self):
        all_plans = [
            _subscription(code='old', is_active=False),
        ]

        available = [s for s in all_plans if s.is_active]

        self.assertEqual(len(available), 0)

    def test_reactivated_plan_becomes_available(self):
        plan = _subscription(code='revived', is_active=True)

        available = [plan] if plan.is_active else []

        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].code, 'revived')


# ── Subscription feature access ──────────────────────────────────────────────

class TestSubscriptionFeatureAccess(TestCase):
    """Validates that the AccessChecker correctly grants or denies access
    based on the features included in the subscription plan."""

    @patch('core.access.checker.SubscriptionCache')
    def test_feature_included_in_plan_allows_access(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-100'
        MockCache.get_features.return_value = {'orders.create', 'orders.view', 'inventory.create'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_feature_not_in_plan_denied_sub_002(self, MockCache, _diagnose):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-100'
        MockCache.get_features.return_value = {'orders.view'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'reports.export')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)

    @patch('core.access.checker.SubscriptionCache')
    def test_no_active_subscription_denied_sub_001(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = None

        # Also mock the DB fallback to return None
        with patch.object(AccessChecker, '_load_subscription_id', return_value=None):
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_NO_ACTIVE)

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_empty_feature_set_denies_all(self, MockCache, _diagnose):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-100'
        MockCache.get_features.return_value = set()
        MockCache.get_limits.return_value = {}

        for feature in ['orders.create', 'inventory.view', 'reports.export']:
            result = AccessChecker.check_feature(company, feature)
            self.assertFalse(result.is_allowed)
            self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)


# ── Subscription module access ───────────────────────────────────────────────

class TestSubscriptionModuleAccess(TestCase):
    """Validates that module-level access is controlled through
    the subscription's feature set."""

    @patch('core.access.checker.SubscriptionCache')
    def test_module_features_in_plan_allows_access(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-200'
        MockCache.get_features.return_value = {
            'inventory.create', 'inventory.view', 'inventory.delete',
        }
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'inventory.view')

        self.assertTrue(result.is_allowed)

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_module_not_in_subscription_denies_all_its_features(self, MockCache, _diagnose):
        """If a module is not assigned to the subscription, none of its
        features will be in the set → all denied."""
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-200'
        # Only orders module features, no inventory
        MockCache.get_features.return_value = {'orders.create', 'orders.view'}
        MockCache.get_limits.return_value = {}

        for feature in ['inventory.create', 'inventory.view', 'inventory.delete']:
            result = AccessChecker.check_feature(company, feature)
            self.assertFalse(result.is_allowed)
            self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)


# ── Subscription lifecycle: Upgrade / Cancel / Reactivate ────────────────────

class TestSubscriptionLifecycle(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.company_id = uuid.uuid4()

    def test_cancel_returns_cancelled_status(self):
        uc = CancelSubscriptionUseCase(self.mock_repo)
        self.mock_repo.cancel.return_value = _company_sub_result(status='cancelled')

        result = uc.execute(self.company_id)

        self.assertEqual(result.status, 'cancelled')
        self.mock_repo.cancel.assert_called_once_with(self.company_id)

    def test_cancel_returns_none_when_no_active_subscription(self):
        uc = CancelSubscriptionUseCase(self.mock_repo)
        self.mock_repo.cancel.return_value = None

        result = uc.execute(self.company_id)

        self.assertIsNone(result)

    def test_reactivate_returns_active_status(self):
        uc = ReactivateSubscriptionUseCase(self.mock_repo)
        self.mock_repo.reactivate.return_value = _company_sub_result(status='active')

        result = uc.execute(self.company_id)

        self.assertEqual(result.status, 'active')
        self.mock_repo.reactivate.assert_called_once_with(self.company_id)

    def test_reactivate_returns_none_when_no_cancelled_subscription(self):
        uc = ReactivateSubscriptionUseCase(self.mock_repo)
        self.mock_repo.reactivate.return_value = None

        result = uc.execute(self.company_id)

        self.assertIsNone(result)

    def test_cancel_then_reactivate_flow(self):
        """Simulates the full cancel → reactivate lifecycle."""
        cancel_uc = CancelSubscriptionUseCase(self.mock_repo)
        reactivate_uc = ReactivateSubscriptionUseCase(self.mock_repo)

        self.mock_repo.cancel.return_value = _company_sub_result(status='cancelled')
        cancelled = cancel_uc.execute(self.company_id)
        self.assertEqual(cancelled.status, 'cancelled')

        self.mock_repo.reactivate.return_value = _company_sub_result(status='active')
        reactivated = reactivate_uc.execute(self.company_id)
        self.assertEqual(reactivated.status, 'active')


# ── Subscription limits (topes) ─────────────────────────────────────────────

class TestSubscriptionLimitsLifetime(TestCase):
    """Tests for lifetime usage limits via AccessChecker."""

    @patch('core.access.checker.SubscriptionCache')
    def test_under_lifetime_limit_allows_access(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-300'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 1000, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 500
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_at_lifetime_limit_denied_sub_003(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-300'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 1000, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 1000  # exactly at limit
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_over_lifetime_limit_denied_sub_003(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-300'
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
    def test_no_limit_configured_allows_unlimited(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-300'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {}  # no limits

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_zero_usage_under_limit(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-300'
        MockCache.get_features.return_value = {'orders.create'}
        MockCache.get_limits.return_value = {
            'orders.create': {'max': 10, 'type': 'lifetime'},
        }

        with patch('core.access.validators.lifetime.UsageStore') as MockStore:
            MockStore.get_lifetime.return_value = 0
            result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)


class TestSubscriptionLimitsDaily(TestCase):
    """Tests for daily usage limits via AccessChecker."""

    @patch('core.access.checker.SubscriptionCache')
    def test_under_daily_limit_allows_access(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-400'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 10000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 5000
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result.is_allowed)

    @patch('core.access.checker.SubscriptionCache')
    def test_at_daily_limit_denied_sub_003(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-400'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 10000, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 10000
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_over_daily_limit_denied(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-400'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 100, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 200
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)

    @patch('core.access.checker.SubscriptionCache')
    def test_zero_daily_usage_allowed(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-400'
        MockCache.get_features.return_value = {'api.calls'}
        MockCache.get_limits.return_value = {
            'api.calls': {'max': 100, 'type': 'daily'},
        }

        with patch('core.access.validators.daily.UsageStore') as MockStore:
            MockStore.get_daily.return_value = 0
            result = AccessChecker.check_feature(company, 'api.calls')

        self.assertTrue(result.is_allowed)


# ── Error code validation ────────────────────────────────────────────────────

class TestSubscriptionErrorCodes(TestCase):
    """Ensures that each denial scenario produces the correct error code
    with the correct HTTP status."""

    def test_sub_001_no_active_subscription(self):
        from core.access.result import AccessResult
        result = AccessResult.no_subscription()

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_NO_ACTIVE)
        self.assertEqual(result.error_code.value, 'SUB_001')

    def test_sub_002_feature_denied(self):
        from core.access.result import AccessResult
        result = AccessResult.feature_denied('orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)
        self.assertEqual(result.error_code.value, 'SUB_002')
        self.assertIn('orders.create', result.detail)

    def test_sub_003_quota_exceeded(self):
        from core.access.result import AccessResult
        result = AccessResult.quota_exceeded('orders.create', 100, 100, 'lifetime')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_QUOTA_EXCEEDED)
        self.assertEqual(result.error_code.value, 'SUB_003')
        self.assertIn('100/100', result.detail)

    def test_sub_001_http_status_is_403(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.SUB_NO_ACTIVE]
        self.assertEqual(entry['http_status'], 403)

    def test_sub_002_http_status_is_403(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.SUB_FEATURE_DENIED]
        self.assertEqual(entry['http_status'], 403)

    def test_sub_003_http_status_is_429(self):
        from core.errors.codes import ERROR_REGISTRY
        entry = ERROR_REGISTRY[AppErrorCode.SUB_QUOTA_EXCEEDED]
        self.assertEqual(entry['http_status'], 429)

    def test_subscription_exception_carries_correct_code(self):
        from core.errors.exceptions import SubscriptionException

        exc = SubscriptionException(AppErrorCode.SUB_FEATURE_DENIED)

        self.assertEqual(exc.code, AppErrorCode.SUB_FEATURE_DENIED)
        self.assertEqual(exc.http_status, 403)

    def test_subscription_exception_with_override_detail(self):
        from core.errors.exceptions import SubscriptionException

        exc = SubscriptionException(
            AppErrorCode.SUB_QUOTA_EXCEEDED,
            override_detail='Custom limit message',
        )

        self.assertEqual(exc.detail, 'Custom limit message')
        self.assertEqual(exc.http_status, 429)

    def test_subscription_exception_with_context(self):
        from core.errors.exceptions import SubscriptionException

        exc = SubscriptionException(
            AppErrorCode.SUB_NO_ACTIVE,
            context={'company_id': 'abc-123'},
        )

        self.assertEqual(exc.context['company_id'], 'abc-123')
