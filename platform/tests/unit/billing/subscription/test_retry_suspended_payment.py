"""Unit tests for RetrySuspendedPaymentUseCase."""
import uuid
from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode
from core.errors.exceptions import (
    NotFoundException,
    PermissionException,
    SubscriptionException,
    ValidationAppException,
)
from platform.features.billing.commerce.payments.domain.enums import ChargeStatus
from platform.features.billing.subscription.subscription.application.retry_suspended_payment import (
    RetrySuspendedPaymentUseCase,
)
from platform.features.billing.subscription.subscription.domain.schemas import (
    CompanySubscriptionResultSchema,
    RetrySuspendedPaymentInputSchema,
    SubscriptionSchema,
)


def _suspended_result(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        subscription_name='Pro',
        start_date=datetime(2027, 1, 1),
        ends_at=datetime(2027, 2, 1),
        status='suspended',
        billing_interval='monthly',
    )
    defaults.update(overrides)
    return CompanySubscriptionResultSchema(**defaults)


def _admin_user():
    user = MagicMock()
    role = MagicMock()
    role.name = 'Administrator'
    user.rol = role
    return user


class TestRetrySuspendedPaymentUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.charge_uc = MagicMock()
        self.directory = MagicMock()
        self.uc = RetrySuspendedPaymentUseCase(
            self.repo, self.charge_uc, directory=self.directory,
        )
        self.company_id = uuid.uuid4()
        self.actor = _admin_user()

    def _data(self, **overrides):
        defaults = dict(
            company_id=self.company_id,
            access_mode='billing_recovery',
        )
        defaults.update(overrides)
        return RetrySuspendedPaymentInputSchema(**defaults)

    def test_non_admin_denied(self):
        user = MagicMock()
        user.rol = MagicMock(name='Operador')
        user.rol.name = 'Operador'

        with self.assertRaises(PermissionException) as ctx:
            self.uc.execute(self._data(), actor_user=user)

        self.assertEqual(ctx.exception.code, AppErrorCode.PERM_INSUFFICIENT)

    def test_full_access_mode_denied(self):
        with self.assertRaises(SubscriptionException) as ctx:
            self.uc.execute(self._data(access_mode='full'), actor_user=self.actor)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_NO_ACTIVE)

    def test_no_suspended_raises_sub_007(self):
        self.repo.get_suspended_acquisition.return_value = None
        self.repo.get_active_acquisition.return_value = None

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(self._data(), actor_user=self.actor)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_NO_SUSPENDED)

    def test_idempotent_when_already_active(self):
        active = _suspended_result(status='active')
        self.repo.get_suspended_acquisition.return_value = None
        self.repo.get_active_acquisition.return_value = active

        result = self.uc.execute(self._data(), actor_user=self.actor)

        self.assertEqual(result, active)

    def test_missing_payment_method_raises_validation(self):
        suspended = _suspended_result()
        self.repo.get_suspended_acquisition.return_value = suspended
        self.repo.get_by_id.return_value = SubscriptionSchema(
            id=suspended.subscription_id,
            name='Pro',
            price=Decimal('99'),
            code='pro',
            is_active=True,
        )
        self.repo.get_annual_discount_percent.return_value = Decimal('0')
        self.directory.active_card.return_value = None

        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(self._data(), actor_user=self.actor)

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)

    @patch('platform.features.billing.commerce.promotion.composition.after_successful_renewal_charge')
    @patch('platform.features.billing.commerce.promotion.composition.get_renewal_charge_amount')
    @patch('platform.features.billing.subscription.subscription.application.retry_suspended_payment.charge_plan')
    def test_successful_charge_restores(self, mock_charge_plan, mock_renewal, mock_after):
        suspended = _suspended_result()
        restored = _suspended_result(status='active')
        self.repo.get_suspended_acquisition.return_value = suspended
        self.repo.get_by_id.return_value = SubscriptionSchema(
            id=suspended.subscription_id,
            name='Pro',
            price=Decimal('99'),
            code='pro',
            is_active=True,
        )
        self.repo.get_annual_discount_percent.return_value = Decimal('0')
        card = MagicMock(id=uuid.uuid4())
        self.directory.active_card.return_value = card
        mock_renewal.return_value = (Decimal('99'), {}, False)
        charge = MagicMock(id=uuid.uuid4(), status=ChargeStatus.CAPTURED)
        mock_charge_plan.return_value = charge
        self.repo.restore_after_payment.return_value = restored

        result = self.uc.execute(self._data(), actor_user=self.actor)

        self.assertEqual(result, restored)
        self.repo.restore_after_payment.assert_called_once_with(
            self.company_id, charge_id=charge.id,
        )
        mock_after.assert_called_once()
