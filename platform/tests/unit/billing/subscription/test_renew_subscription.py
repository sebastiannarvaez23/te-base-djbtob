"""High-precision unit tests for RenewSubscriptionUseCase (automatic recurring
renewal). Money-touching, so the tests assert the exact behaviour: charge with
the EMPTY metadata (→ default SUB_INVOICING email + attached invoice), charge
BEFORE extending the vigencia, and suspension + SUB_SUSPENDED on any failure.

All collaborators mocked — no DB, no gateway, no event bus, no email."""
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.payments.domain.enums import ChargeStatus, MethodType
from platform.features.billing.subscription.subscription.application.renew_subscription import (
    RenewSubscriptionUseCase,
)

pytestmark = pytest.mark.unit


def _plan(price, name='Plan'):
    return SimpleNamespace(id=uuid.uuid4(), name=name, price=Decimal(str(price)))


def _charge(status=ChargeStatus.CAPTURED):
    return SimpleNamespace(id=uuid.uuid4(), status=status, failure_message='')


def _result():
    return SimpleNamespace(subscription_name='Plan', status='active')


_UNSET = object()


class _Base(TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.repo.get_annual_discount_percent.return_value = Decimal('15')
        self.charge = MagicMock()
        self.notification = MagicMock()
        self.admin = SimpleNamespace(first_name='Ana', last_name='Gómez', email='admin@acme.com')
        self.company = SimpleNamespace(name='Acme S.A.S')
        self.card = SimpleNamespace(id='card1')
        self.company_id = uuid.uuid4()
        self.repo.activate_plan.return_value = _result()
        self.repo.active_billing_interval.return_value = 'monthly'
        self.charge.execute.return_value = _charge(ChargeStatus.CAPTURED)

        promo_amount = patch(
            'platform.features.billing.commerce.promotion.application.renewal_integration.get_renewal_charge_amount',
            side_effect=lambda _repo, _cid, price, **_kwargs: (price, {}, False),
        )
        promo_after = patch(
            'platform.features.billing.commerce.promotion.application.renewal_integration.after_successful_renewal_charge',
        )
        self._promo_amount_mock = promo_amount.start()
        self._promo_after_mock = promo_after.start()
        self.addCleanup(promo_amount.stop)
        self.addCleanup(promo_after.stop)

    def _uc(self, admin=_UNSET, card=_UNSET):
        directory = MagicMock()
        directory.admin_of.return_value = self.admin if admin is _UNSET else admin
        directory.company.return_value = self.company
        directory.active_card.return_value = self.card if card is _UNSET else card
        return RenewSubscriptionUseCase(
            self.repo, self.charge, notification=self.notification, directory=directory,
        )

    def _due(self, plan):
        self.repo.get_renewal_due.return_value = plan.id
        self.repo.get_by_id.return_value = plan


class TestRenewHappyPath(_Base):

    def test_not_due_is_noop(self):
        self.repo.get_renewal_due.return_value = None
        self.assertEqual(self._uc().renew_for_company(self.company_id), 'not_due')
        self.charge.execute.assert_not_called()
        self.repo.activate_plan.assert_not_called()
        self.repo.suspend.assert_not_called()

    def test_free_plan_extends_without_charge(self):
        plan = _plan(0, 'Free')
        self._due(plan)
        self.assertEqual(self._uc().renew_for_company(self.company_id), 'renewed')
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, plan.id, billing_interval='monthly',
        )
        self.charge.execute.assert_not_called()

    def test_charges_then_extends_in_order(self):
        """Charge first (so the auto-invoice links the active plan), then extend."""
        order = []
        plan = _plan(50, 'Pro')
        self._due(plan)
        charge = _charge()
        self.charge.execute.side_effect = lambda *a, **k: order.append('charge') or charge
        self.repo.activate_plan.side_effect = lambda *a, **k: order.append('extend') or _result()

        self.assertEqual(self._uc().renew_for_company(self.company_id), 'renewed')

        self.assertEqual(order, ['charge', 'extend'])
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, plan.id, billing_interval='monthly', charge_id=charge.id,
        )
        self.repo.suspend.assert_not_called()

    def test_charge_uses_empty_metadata_for_default_invoicing(self):
        plan = _plan(Decimal('49.99'), 'Pro')
        self._due(plan)
        self._uc().renew_for_company(self.company_id)
        args, kwargs = self.charge.execute.call_args
        request = args[0]
        self.assertEqual(request.metadata, {'billing_interval': 'monthly'})            # → default SUB_INVOICING (not SUB_UPGRADE)
        self.assertEqual(request.amount, Decimal('49.99'))
        self.assertEqual(request.method_type, MethodType.CARD)
        self.assertEqual(kwargs['payment_method_id'], 'card1')

    def test_due_company_ids_delegates_to_repo(self):
        self.repo.list_renewals_due.return_value = ['c1', 'c2']
        self.assertEqual(self._uc().due_company_ids(), ['c1', 'c2'])


class TestRenewFailureSuspends(_Base):

    def test_no_card_suspends_without_charge(self):
        plan = _plan(50, 'Pro')
        self._due(plan)
        self.assertEqual(self._uc(card=None).renew_for_company(self.company_id), 'suspended')
        self.charge.execute.assert_not_called()
        self.repo.suspend.assert_called_once_with(self.company_id)
        self.repo.activate_plan.assert_not_called()

    def test_declined_charge_suspends_and_does_not_extend(self):
        plan = _plan(50, 'Pro')
        self._due(plan)
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)
        self.assertEqual(self._uc().renew_for_company(self.company_id), 'suspended')
        self.repo.suspend.assert_called_once_with(self.company_id)
        self.repo.activate_plan.assert_not_called()

    def test_gateway_exception_suspends(self):
        plan = _plan(50, 'Pro')
        self._due(plan)
        self.charge.execute.side_effect = RuntimeError('gateway boom')
        self.assertEqual(self._uc().renew_for_company(self.company_id), 'suspended')
        self.repo.suspend.assert_called_once_with(self.company_id)
        self.repo.activate_plan.assert_not_called()

    def test_suspend_sends_sub_suspended_to_admin(self):
        plan = _plan(50, 'Empresarial')
        self._due(plan)
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)
        self._uc().renew_for_company(self.company_id)
        _, kwargs = self.notification.send_email.call_args
        self.assertEqual(kwargs['template_code'], 'SUB_SUSPENDED')
        self.assertEqual(kwargs['to'], ['admin@acme.com'])
        self.assertEqual(kwargs['context']['subscription_name'], 'Empresarial')
        self.assertEqual(kwargs['context']['total_due'], 50.0)

    def test_suspend_without_admin_skips_email_but_still_suspends(self):
        plan = _plan(50, 'Pro')
        self._due(plan)
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)
        self._uc(admin=None).renew_for_company(self.company_id)
        self.repo.suspend.assert_called_once_with(self.company_id)
        self.notification.send_email.assert_not_called()


class TestRenewWithActivePromotion(_Base):
    """Automatic renewal must honour an active promotion benefit."""

    def test_active_discount_charges_reduced_amount_and_decrements(self):
        plan = _plan(Decimal('100.00'), 'Pro')
        self._due(plan)
        promo_meta = {
            'voucher_type': 'DISCOUNT',
            'promotion_serial': 'WLGX-DSC-RNW001',
            'original_amount': '100.00',
            'discount_amount': '20.00',
        }
        self._promo_amount_mock.side_effect = lambda _repo, _cid, price, **_kwargs: (
            Decimal('80.00'), promo_meta, False,
        )

        self.assertEqual(self._uc().renew_for_company(self.company_id), 'renewed')

        args, kwargs = self.charge.execute.call_args
        request = args[0]
        self.assertEqual(request.amount, Decimal('80.00'))
        self.assertEqual(request.metadata['voucher_type'], 'DISCOUNT')
        self.assertEqual(request.metadata['billing_interval'], 'monthly')
        self.assertEqual(request.metadata['original_amount'], '100.00')
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, plan.id, billing_interval='monthly',
            charge_id=self.charge.execute.return_value.id,
        )
        self._promo_after_mock.assert_called_once()
        after_args, after_kwargs = self._promo_after_mock.call_args
        self.assertEqual(after_args[1], self.company_id)
        self.assertEqual(after_kwargs['plan_id'], plan.id)

    def test_active_gift_skips_charge_and_extends_without_decrement(self):
        plan = _plan(Decimal('100.00'), 'Pro')
        self._due(plan)
        self._promo_amount_mock.side_effect = lambda _repo, _cid, price, **_kwargs: (
            Decimal('0'), {'voucher_type': 'GIFT'}, True,
        )

        self.assertEqual(self._uc().renew_for_company(self.company_id), 'renewed')

        self.charge.execute.assert_not_called()
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, plan.id, billing_interval='monthly',
        )
        self.repo.suspend.assert_not_called()
        self._promo_after_mock.assert_not_called()

    def test_failed_discount_charge_does_not_decrement_cycles(self):
        plan = _plan(Decimal('100.00'), 'Pro')
        self._due(plan)
        self._promo_amount_mock.side_effect = lambda _repo, _cid, price, **_kwargs: (
            Decimal('80.00'), {'voucher_type': 'DISCOUNT'}, False,
        )
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)

        self.assertEqual(self._uc().renew_for_company(self.company_id), 'suspended')

        self.repo.activate_plan.assert_not_called()
        self._promo_after_mock.assert_not_called()


class TestRenewYearly(_Base):

    def test_renews_with_yearly_amount_and_interval(self):
        plan = _plan(Decimal('100.00'), 'Pro')
        self._due(plan)
        self.repo.active_billing_interval.return_value = 'yearly'

        self.assertEqual(self._uc().renew_for_company(self.company_id), 'renewed')

        request = self.charge.execute.call_args.args[0]
        self.assertEqual(request.amount, Decimal('1020.00'))
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, plan.id, billing_interval='yearly',
            charge_id=self.charge.execute.return_value.id,
        )
