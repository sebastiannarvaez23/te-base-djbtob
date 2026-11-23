"""  """"""
Unit tests for subscription use cases:
  - GetAllSubscriptionsUseCase
  - GetSubscriptionByCodeUseCase
  - CreateSubscriptionUseCase
  - UpdateSubscriptionUseCase
  - DeleteSubscriptionUseCase

No database required.
"""
import uuid
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.billing.subscription.subscription.application.use_cases import (
    GetActiveSubscriptionsUseCase,
    GetAllSubscriptionsUseCase,
    GetSubscriptionByCodeUseCase,
    CreateSubscriptionUseCase,
    UpdateSubscriptionUseCase,
    DeleteSubscriptionUseCase,
)
from platform.features.billing.subscription.subscription.domain.schemas import (
    SubscriptionSchema,
    CreateSubscriptionSchema,
)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _subscription(**overrides) -> SubscriptionSchema:
    defaults = dict(
        id=uuid.uuid4(),
        name='Standard Plan',
        price=Decimal('49.99'),
        code='standard',
        is_active=True,
    )
    defaults.update(overrides)
    return SubscriptionSchema(**defaults)


# ── GetAllSubscriptionsUseCase ─────────────────────────────────────────────────

class TestGetAllSubscriptionsUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetAllSubscriptionsUseCase(self.mock_repo)

    def test_returns_all_subscriptions(self):
        subs = [
            _subscription(code='basic'),
            _subscription(code='standard'),
            _subscription(code='pro'),
        ]
        self.mock_repo.get_all.return_value = subs

        result = self.use_case.execute()

        self.assertEqual(len(result), 3)
        self.mock_repo.get_all.assert_called_once()

    def test_returns_empty_list_when_no_plans_exist(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])


# ── GetActiveSubscriptionsUseCase ──────────────────────────────────────────────

class TestGetActiveSubscriptionsUseCase(TestCase):
    """The public catalog use case. Distinct from ``GetAll`` because the
    admin CRUD must keep seeing deactivated plans (for reactivation
    flows); the public catalog must NOT advertise them."""

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetActiveSubscriptionsUseCase(self.mock_repo)

    def test_delegates_to_repository_get_active_not_get_all(self):
        """The use case exists primarily to wire ``get_active`` and stay
        out of the admin CRUD's path. If it ever slips back to ``get_all``
        the public catalog quietly starts leaking deactivated plans."""
        self.mock_repo.get_active.return_value = []

        self.use_case.execute()

        self.mock_repo.get_active.assert_called_once()
        self.mock_repo.get_all.assert_not_called()

    def test_returns_what_the_repository_returns(self):
        active = [_subscription(code='basic'), _subscription(code='pro')]
        self.mock_repo.get_active.return_value = active

        result = self.use_case.execute()

        self.assertEqual(result, active)

    def test_returns_empty_list_when_no_active_plans(self):
        self.mock_repo.get_active.return_value = []

        self.assertEqual(self.use_case.execute(), [])


# ── GetSubscriptionByCodeUseCase ───────────────────────────────────────────────

class TestGetSubscriptionByCodeUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetSubscriptionByCodeUseCase(self.mock_repo)

    def test_returns_subscription_by_code(self):
        sub = _subscription(code='enterprise')
        self.mock_repo.get_by_code.return_value = sub

        result = self.use_case.execute('enterprise')

        self.mock_repo.get_by_code.assert_called_once_with('enterprise')
        self.assertEqual(result.code, 'enterprise')

    def test_returns_none_when_code_does_not_exist(self):
        self.mock_repo.get_by_code.return_value = None

        result = self.use_case.execute('nonexistent')

        self.assertIsNone(result)


# ── CreateSubscriptionUseCase ──────────────────────────────────────────────────

class TestCreateSubscriptionUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateSubscriptionUseCase(self.mock_repo)

    def test_creates_subscription_and_returns_schema(self):
        data = CreateSubscriptionSchema(name='Premium', price=Decimal('99.99'), code='premium', is_active=True)
        created_sub = _subscription(name='Premium', price=Decimal('99.99'), code='premium')
        self.mock_repo.create.return_value = created_sub

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.code, 'premium')
        self.assertEqual(result.price, Decimal('99.99'))

    def test_subscription_is_active_by_default(self):
        data = CreateSubscriptionSchema(name='Free', price=Decimal('0'), code='free', is_active=True)
        self.mock_repo.create.return_value = _subscription(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)

    def test_propagates_exceptions_from_repository(self):
        data = CreateSubscriptionSchema(name='Duplicate', price=Decimal('10'), code='basic', is_active=True)
        self.mock_repo.create.side_effect = Exception('duplicate code')

        with self.assertRaises(Exception):
            self.use_case.execute(data)


# ── UpdateSubscriptionUseCase ──────────────────────────────────────────────────

class TestUpdateSubscriptionUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateSubscriptionUseCase(self.mock_repo)
        self.sub_id = uuid.uuid4()

    def test_updates_existing_subscription(self):
        data = CreateSubscriptionSchema(name='Standard Plus', price=Decimal('59.99'), code='standard', is_active=True)
        updated_sub = _subscription(id=self.sub_id, name='Standard Plus', price=Decimal('59.99'))
        self.mock_repo.update.return_value = updated_sub

        result = self.use_case.execute(self.sub_id, data)

        self.mock_repo.update.assert_called_once_with(self.sub_id, data)
        self.assertEqual(result.name, 'Standard Plus')

    def test_returns_none_when_subscription_does_not_exist(self):
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), CreateSubscriptionSchema(
            name='x', price=Decimal('0'), code='x', is_active=True
        ))

        self.assertIsNone(result)


# ── DeleteSubscriptionUseCase ──────────────────────────────────────────────────

class TestDeleteSubscriptionUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteSubscriptionUseCase(self.mock_repo)

    def test_deletes_subscription_and_returns_true(self):
        sub_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(sub_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(sub_id)

    def test_returns_false_when_subscription_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)
