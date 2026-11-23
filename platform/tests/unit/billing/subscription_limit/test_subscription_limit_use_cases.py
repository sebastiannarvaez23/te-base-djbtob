"""
Unit tests for SubscriptionLimit use cases:
  - GetAllSubscriptionLimitsUseCase
  - GetSubscriptionLimitsBySubscriptionUseCase
  - GetSubscriptionLimitByIdUseCase
  - CreateSubscriptionLimitUseCase
  - UpdateSubscriptionLimitUseCase
  - DeleteSubscriptionLimitUseCase
  - Limit linked to functionality validation
  - Validation type (daily / lifetime) behavior
  - Duplicate limit detection (unique_together)

No database required.
"""
import uuid
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.billing.subscription.subscription_limit.application.use_cases import (
    CreateSubscriptionLimitUseCase,
    DeleteSubscriptionLimitUseCase,
    GetAllSubscriptionLimitsUseCase,
    GetSubscriptionLimitByIdUseCase,
    GetSubscriptionLimitsBySubscriptionUseCase,
    UpdateSubscriptionLimitUseCase,
)
from platform.features.billing.subscription.subscription_limit.domain.schemas import (
    CreateSubscriptionLimitSchema,
    SubscriptionLimitSchema,
    UpdateSubscriptionLimitSchema,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _limit(**overrides) -> SubscriptionLimitSchema:
    defaults = dict(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        functionality_id=uuid.uuid4(),
        subscription_name='Plan Profesional',
        functionality_key='orders.create',
        functionality_label='Crear Pedidos',
        functionality_module_code='orders',
        name='Tope de Pedidos',
        max_value=1000,
        validation_type='lifetime',
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return SubscriptionLimitSchema(**defaults)


# ── GetAllSubscriptionLimitsUseCase ──────────────────────────────────────────

class TestGetAllSubscriptionLimitsUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetAllSubscriptionLimitsUseCase(self.mock_repo)

    def test_returns_all_limits(self):
        limits = [
            _limit(functionality_key='orders.create'),
            _limit(functionality_key='api.calls', validation_type='daily'),
            _limit(functionality_key='storage.upload'),
        ]
        self.mock_repo.get_all.return_value = limits

        result = self.use_case.execute()

        self.assertEqual(len(result), 3)
        self.mock_repo.get_all.assert_called_once()

    def test_returns_empty_list_when_no_limits(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])

    def test_returns_limits_with_different_validation_types(self):
        limits = [
            _limit(validation_type='lifetime'),
            _limit(validation_type='daily'),
        ]
        self.mock_repo.get_all.return_value = limits

        result = self.use_case.execute()

        types = [l.validation_type for l in result]
        self.assertIn('lifetime', types)
        self.assertIn('daily', types)


# ── GetSubscriptionLimitsBySubscriptionUseCase ───────────────────────────────

class TestGetSubscriptionLimitsBySubscriptionUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetSubscriptionLimitsBySubscriptionUseCase(self.mock_repo)

    def test_returns_limits_for_subscription(self):
        sub_id = uuid.uuid4()
        limits = [
            _limit(subscription_id=sub_id, functionality_key='orders.create'),
            _limit(subscription_id=sub_id, functionality_key='orders.view'),
        ]
        self.mock_repo.get_by_subscription.return_value = limits

        result = self.use_case.execute(sub_id)

        self.assertEqual(len(result), 2)
        self.mock_repo.get_by_subscription.assert_called_once_with(sub_id, filters=None)

    def test_returns_empty_list_for_subscription_without_limits(self):
        sub_id = uuid.uuid4()
        self.mock_repo.get_by_subscription.return_value = []

        result = self.use_case.execute(sub_id)

        self.assertEqual(result, [])

    def test_limits_belong_to_correct_subscription(self):
        sub_id = uuid.uuid4()
        limits = [_limit(subscription_id=sub_id) for _ in range(3)]
        self.mock_repo.get_by_subscription.return_value = limits

        result = self.use_case.execute(sub_id)

        for limit in result:
            self.assertEqual(limit.subscription_id, sub_id)


# ── GetSubscriptionLimitByIdUseCase ──────────────────────────────────────────

class TestGetSubscriptionLimitByIdUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetSubscriptionLimitByIdUseCase(self.mock_repo)

    def test_returns_limit_by_id(self):
        limit_id = uuid.uuid4()
        limit = _limit(id=limit_id, functionality_key='orders.create')
        self.mock_repo.get_by_id.return_value = limit

        result = self.use_case.execute(limit_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, limit_id)
        self.assertEqual(result.functionality_key, 'orders.create')

    def test_returns_none_when_not_found(self):
        self.mock_repo.get_by_id.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)

    def test_returned_limit_has_functionality_metadata(self):
        limit = _limit(
            functionality_key='inventory.create',
            functionality_label='Crear inventario',
            functionality_module_code='inventory',
        )
        self.mock_repo.get_by_id.return_value = limit

        result = self.use_case.execute(limit.id)

        self.assertEqual(result.functionality_key, 'inventory.create')
        self.assertEqual(result.functionality_label, 'Crear inventario')
        self.assertEqual(result.functionality_module_code, 'inventory')


# ── CreateSubscriptionLimitUseCase ───────────────────────────────────────────

class TestCreateSubscriptionLimitUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateSubscriptionLimitUseCase(self.mock_repo)

    def test_creates_lifetime_limit(self):
        sub_id = uuid.uuid4()
        func_id = uuid.uuid4()
        data = CreateSubscriptionLimitSchema(
            subscription_id=sub_id,
            functionality_id=func_id,
            name='Tope de Pedidos',
            max_value=500,
            validation_type='lifetime',
        )
        created = _limit(
            subscription_id=sub_id,
            functionality_id=func_id,
            max_value=500,
            validation_type='lifetime',
        )
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.max_value, 500)
        self.assertEqual(result.validation_type, 'lifetime')

    def test_creates_daily_limit(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            name='Tope de API calls',
            max_value=10000,
            validation_type='daily',
        )
        created = _limit(max_value=10000, validation_type='daily')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.max_value, 10000)
        self.assertEqual(result.validation_type, 'daily')

    def test_creates_window_limit(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            name='Tope de chat por ventana',
            max_value=3,
            validation_type='window',
            window_hours=3,
        )
        created = _limit(max_value=3, validation_type='window', window_hours=3)
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.validation_type, 'window')
        self.assertEqual(result.window_hours, 3)
        self.assertEqual(result.max_value, 3)

    def test_default_validation_type_is_lifetime(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            max_value=100,
        )
        self.assertEqual(data.validation_type, 'lifetime')

    def test_limit_linked_to_functionality(self):
        func_id = uuid.uuid4()
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=func_id,
            max_value=200,
        )
        created = _limit(functionality_id=func_id, functionality_key='orders.create')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.functionality_id, func_id)
        self.assertEqual(result.functionality_key, 'orders.create')

    def test_propagates_exception_on_duplicate(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            max_value=100,
        )
        self.mock_repo.create.side_effect = Exception('UNIQUE constraint failed')

        with self.assertRaises(Exception):
            self.use_case.execute(data)

    def test_limit_with_zero_max_value(self):
        """A max_value of 0 effectively blocks all usage from the start."""
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            max_value=0,
        )
        created = _limit(max_value=0)
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.max_value, 0)

    def test_limit_with_name(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            name='Tope mensual de reportes',
            max_value=50,
        )
        created = _limit(name='Tope mensual de reportes', max_value=50)
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.name, 'Tope mensual de reportes')

    def test_limit_without_name_defaults_to_empty(self):
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            max_value=100,
        )
        self.assertEqual(data.name, '')


# ── UpdateSubscriptionLimitUseCase ───────────────────────────────────────────

class TestUpdateSubscriptionLimitUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateSubscriptionLimitUseCase(self.mock_repo)
        self.limit_id = uuid.uuid4()
        self.existing = _limit(id=self.limit_id, max_value=100, validation_type='lifetime')
        self.mock_repo.get_by_id.return_value = self.existing

    def test_updates_max_value(self):
        data = UpdateSubscriptionLimitSchema(max_value=2000)
        updated = _limit(id=self.limit_id, max_value=2000)
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        self.mock_repo.get_by_id.assert_called_once_with(self.limit_id)
        args = self.mock_repo.update.call_args[0]
        self.assertEqual(args[0], self.limit_id)
        self.assertEqual(args[1].max_value, 2000)
        self.assertIsNone(args[1].window_hours)
        self.assertEqual(result.max_value, 2000)

    def test_updates_validation_type(self):
        data = UpdateSubscriptionLimitSchema(validation_type='daily')
        updated = _limit(id=self.limit_id, validation_type='daily')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        self.assertEqual(result.validation_type, 'daily')
        self.assertIsNone(self.mock_repo.update.call_args[0][1].window_hours)

    def test_updates_to_window_with_hours(self):
        data = UpdateSubscriptionLimitSchema(
            validation_type='window',
            window_hours=6,
        )
        updated = _limit(
            id=self.limit_id,
            validation_type='window',
            window_hours=6,
        )
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        payload = self.mock_repo.update.call_args[0][1]
        self.assertEqual(payload.validation_type, 'window')
        self.assertEqual(payload.window_hours, 6)
        self.assertEqual(result.validation_type, 'window')
        self.assertEqual(result.window_hours, 6)

    def test_updates_to_window_reuses_existing_hours(self):
        self.mock_repo.get_by_id.return_value = _limit(
            id=self.limit_id, validation_type='window', window_hours=3,
        )
        data = UpdateSubscriptionLimitSchema(validation_type='window')
        updated = _limit(id=self.limit_id, validation_type='window', window_hours=3)
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        payload = self.mock_repo.update.call_args[0][1]
        self.assertEqual(payload.window_hours, 3)
        self.assertEqual(result.window_hours, 3)

    def test_updates_to_window_without_hours_raises(self):
        from core.errors import ValidationAppException

        data = UpdateSubscriptionLimitSchema(validation_type='window')
        with self.assertRaises(ValidationAppException):
            self.use_case.execute(self.limit_id, data)
        self.mock_repo.update.assert_not_called()

    def test_updates_name(self):
        data = UpdateSubscriptionLimitSchema(name='Nombre nuevo')
        updated = _limit(id=self.limit_id, name='Nombre nuevo')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        self.assertEqual(result.name, 'Nombre nuevo')

    def test_returns_none_when_not_found(self):
        self.mock_repo.get_by_id.return_value = None
        data = UpdateSubscriptionLimitSchema(max_value=999)

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)
        self.mock_repo.update.assert_not_called()

    def test_partial_update_preserves_other_fields(self):
        data = UpdateSubscriptionLimitSchema(max_value=999)
        updated = _limit(
            id=self.limit_id,
            max_value=999,
            validation_type='lifetime',
            name='Original',
        )
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.limit_id, data)

        self.assertEqual(result.max_value, 999)
        self.assertEqual(result.validation_type, 'lifetime')
        self.assertEqual(result.name, 'Original')

    def test_create_duplicate_raises_conflict(self):
        from django.db import IntegrityError
        from core.errors import ConflictException

        create_uc = CreateSubscriptionLimitUseCase(self.mock_repo)
        data = CreateSubscriptionLimitSchema(
            subscription_id=uuid.uuid4(),
            functionality_id=uuid.uuid4(),
            max_value=1,
        )
        self.mock_repo.create.side_effect = IntegrityError('unique')

        with self.assertRaises(ConflictException):
            create_uc.execute(data)


# ── DeleteSubscriptionLimitUseCase ───────────────────────────────────────────

class TestDeleteSubscriptionLimitUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteSubscriptionLimitUseCase(self.mock_repo)

    def test_deletes_limit_and_returns_true(self):
        limit_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(limit_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(limit_id)

    def test_returns_false_when_not_found(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)
