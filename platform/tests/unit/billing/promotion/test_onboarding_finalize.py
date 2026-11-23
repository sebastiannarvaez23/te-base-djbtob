"""Unit tests: onboarding gift redeem must not depend on a payment token.

Regression: GIFT skips the payment step, so ``processor_token`` is absent.
``OnboardingBillingService`` must still redeem and create the ACTIVE benefit
path (via RedeemVoucherUseCase); PM/charge only when a token exists.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from platform.features.billing.commerce.promotion.application.onboarding_finalize import (
    OnboardingBillingService,
)
from platform.features.billing.commerce.promotion.domain.schemas import ActiveBenefitSchema
from platform.features.billing.commerce.promotion.infrastructure.repositories import (
    _to_active_benefit_schema,
)

pytestmark = pytest.mark.unit


def _gift_preview(**overrides):
    data = {
        'voucher_type': 'GIFT',
        'final_amount': 0,
        'original_amount': 100,
        'discount_amount': 100,
        'benefit_months': 3,
    }
    data.update(overrides)
    return data


def _discount_preview(**overrides):
    data = {
        'voucher_type': 'DISCOUNT',
        'final_amount': 80,
        'original_amount': 100,
        'discount_amount': 20,
        'discount_percent': 20,
    }
    data.update(overrides)
    return data


def _service(*, redeem=None, charge=None, pm=None, catalog=None):
    catalog = catalog or MagicMock()
    catalog.get_active_plan.return_value = SimpleNamespace(name='Pro')
    return OnboardingBillingService(
        redeem_use_case=redeem or MagicMock(),
        charge_port=charge or MagicMock(),
        payment_method_creator=pm or MagicMock(),
        plan_catalog=catalog,
    )


class ProcessOnboardingBillingGiftTests(TestCase):
    """C1 — Gift applied in onboarding, no card collected."""

    def _registration(self, *, serial=None, preview=None, token=None, subscription_id=None):
        sub_id = subscription_id or uuid4()
        payment_data = {}
        if token:
            payment_data = {
                'processor_token': token,
                'holder': 'Ana',
                'last4': '4242',
                'expiry_month': 12,
                'expiry_year': 2030,
            }
        return SimpleNamespace(
            id=uuid4(),
            subscription_id=sub_id,
            requires_payment=False,
            subscription_data={
                'applied_voucher_serial': serial,
                'promotion_preview': preview or {},
                'price': 100,
            },
            payment_data=payment_data,
        )

    def _stub_redeem(self, redeem, preview):
        result = SimpleNamespace(
            redemption=SimpleNamespace(id=uuid4()),
            preview=SimpleNamespace(model_dump=lambda mode='json': preview),
        )
        redeem.execute.return_value = result
        return result

    def test_gift_without_token_still_redeems(self):
        company_id = uuid4()
        serial = 'WLGX-GFT-ONB001'
        preview = _gift_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        self._stub_redeem(redeem, preview)

        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=company_id,
            registration=self._registration(serial=serial, preview=preview),
        )

        redeem.execute.assert_called_once()
        args = redeem.execute.call_args[0][0]
        self.assertEqual(args.serial, serial)
        self.assertEqual(args.context, 'ONBOARDING')
        self.assertEqual(args.company_id, company_id)
        self.assertTrue(str(args.idempotency_key).startswith('onb-'))
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_gift_empty_payment_data_still_redeems(self):
        preview = _gift_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        self._stub_redeem(redeem, preview)
        reg = self._registration(serial='WLGX-GFT-EMPTY', preview=preview)
        reg.payment_data = {}

        _service(redeem=redeem, pm=pm, charge=charge).run(company_id=uuid4(), registration=reg)

        redeem.execute.assert_called_once()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_gift_redeem_failure_is_raised(self):
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        redeem.execute.side_effect = RuntimeError('redeem boom')
        with self.assertRaises(RuntimeError):
            _service(redeem=redeem, pm=pm, charge=charge).run(
                company_id=uuid4(),
                registration=self._registration(serial='WLGX-GFT-FAIL', preview=_gift_preview()),
            )
        redeem.execute.assert_called_once()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_serial_without_subscription_id_skips_redeem(self):
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        reg = self._registration(serial='WLGX-GFT-NOSUB', preview=_gift_preview())
        reg.subscription_id = None

        _service(redeem=redeem, pm=pm, charge=charge).run(company_id=uuid4(), registration=reg)

        redeem.execute.assert_not_called()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_no_serial_no_token_is_noop(self):
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=uuid4(),
            registration=self._registration(),
        )
        redeem.execute.assert_not_called()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_gift_with_token_redeems_and_charges_zero(self):
        """If a card was collected anyway, gift still redeems and charges $0."""
        preview = _gift_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        self._stub_redeem(redeem, preview)
        pm.create_from_onboarding.return_value = 'pm-1'

        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=uuid4(),
            registration=self._registration(serial='WLGX-GFT-CARD', preview=preview, token='tok_gift'),
        )

        redeem.execute.assert_called_once()
        pm.create_from_onboarding.assert_called_once()
        charge.charge_plan.assert_called_once()
        self.assertEqual(charge.charge_plan.call_args.kwargs['amount'], Decimal('0'))
        charge.bind_to_active_period.assert_not_called()

    def test_gift_without_token_does_not_bind_charge(self):
        preview = _gift_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        self._stub_redeem(redeem, preview)

        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=uuid4(),
            registration=self._registration(serial='WLGX-GFT-NOBIND', preview=preview),
        )

        redeem.execute.assert_called_once()
        charge.bind_to_active_period.assert_not_called()


class ProcessOnboardingBillingDiscountTests(TestCase):

    def _registration(self, *, serial, preview, token='tok_test'):
        return SimpleNamespace(
            id=uuid4(),
            subscription_id=uuid4(),
            requires_payment=True,
            subscription_data={
                'applied_voucher_serial': serial,
                'promotion_preview': preview,
                'price': 100,
            },
            payment_data={
                'processor_token': token,
                'holder': 'Ana',
                'last4': '4242',
                'expiry_month': 12,
                'expiry_year': 2030,
            },
        )

    def test_discount_with_token_redeems_and_charges(self):
        preview = _discount_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        redeem.execute.return_value = SimpleNamespace(
            redemption=SimpleNamespace(id=uuid4()),
            preview=SimpleNamespace(model_dump=lambda mode='json': preview),
        )
        pm.create_from_onboarding.return_value = 'pm-1'
        charge_id = uuid4()
        charge.charge_plan.return_value = SimpleNamespace(
            is_captured=True, failure_message='', id=charge_id,
        )
        company_id = uuid4()

        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=company_id,
            registration=self._registration(serial='WLGX-DSC-ONB001', preview=preview),
        )

        pm.create_from_onboarding.assert_called_once()
        charge.charge_plan.assert_called_once()
        self.assertEqual(charge.charge_plan.call_args.kwargs['amount'], Decimal('80'))
        redeem.execute.assert_called_once()
        charge.bind_to_active_period.assert_called_once_with(
            company_id=company_id, charge_id=charge_id,
        )

    def test_discount_bind_failure_does_not_fail_onboarding(self):
        preview = _discount_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        redeem.execute.return_value = SimpleNamespace(
            redemption=SimpleNamespace(id=uuid4()),
            preview=SimpleNamespace(model_dump=lambda mode='json': preview),
        )
        pm.create_from_onboarding.return_value = 'pm-1'
        charge.charge_plan.return_value = SimpleNamespace(
            is_captured=True, failure_message='', id=uuid4(),
        )
        charge.bind_to_active_period.side_effect = RuntimeError('bind boom')

        _service(redeem=redeem, pm=pm, charge=charge).run(
            company_id=uuid4(),
            registration=self._registration(serial='WLGX-DSC-BIND', preview=preview),
        )

        redeem.execute.assert_called_once()
        charge.bind_to_active_period.assert_called_once()

    def test_discount_without_token_refuses_redeem(self):
        """Paid DISCOUNT without token must fail closed (no unpaid benefit)."""
        from core.errors import AppException

        preview = _discount_preview()
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        reg = SimpleNamespace(
            id=uuid4(),
            subscription_id=uuid4(),
            requires_payment=True,
            subscription_data={
                'applied_voucher_serial': 'WLGX-DSC-NOTOK',
                'promotion_preview': preview,
                'price': 100,
            },
            payment_data={},
        )

        with self.assertRaises(AppException):
            _service(redeem=redeem, pm=pm, charge=charge).run(company_id=uuid4(), registration=reg)

        redeem.execute.assert_not_called()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()

    def test_hundred_percent_discount_redeems_like_gift_without_charge(self):
        preview = _discount_preview(
            final_amount=0, discount_amount=100, discount_percent=100,
        )
        redeem, pm, charge = MagicMock(), MagicMock(), MagicMock()
        redeem.execute.return_value = SimpleNamespace(
            redemption=SimpleNamespace(id=uuid4()),
            preview=SimpleNamespace(model_dump=lambda mode='json': preview),
        )
        reg = SimpleNamespace(
            id=uuid4(),
            subscription_id=uuid4(),
            requires_payment=False,
            subscription_data={
                'applied_voucher_serial': 'WLGX-DSC-FREE',
                'promotion_preview': preview,
                'price': 100,
            },
            payment_data={},
        )

        _service(redeem=redeem, pm=pm, charge=charge).run(company_id=uuid4(), registration=reg)

        redeem.execute.assert_called_once()
        pm.create_from_onboarding.assert_not_called()
        charge.charge_plan.assert_not_called()
        charge.bind_to_active_period.assert_not_called()


class ActiveBenefitSchemaGiftTests(TestCase):
    """Settings benefits card must expose gift duration from the voucher."""

    def test_gift_benefit_includes_months_and_serial(self):
        benefit = SimpleNamespace(
            id=uuid4(),
            voucher_type='GIFT',
            subscription_id=uuid4(),
            subscription=SimpleNamespace(name='Professional'),
            benefit_start='2026-07-01T00:00:00Z',
            benefit_end='2026-10-01T00:00:00Z',
            discount_percent=None,
            remaining_discount_cycles=None,
            status='ACTIVE',
            redemption=SimpleNamespace(
                voucher=SimpleNamespace(
                    serial='WLGX-GFT-SHOW01',
                    benefit_months=3,
                    discount_duration_months=1,
                ),
            ),
        )

        schema = _to_active_benefit_schema(benefit)

        self.assertIsInstance(schema, ActiveBenefitSchema)
        self.assertEqual(schema.voucher_type, 'GIFT')
        self.assertEqual(schema.voucher_serial, 'WLGX-GFT-SHOW01')
        self.assertEqual(schema.subscription_name, 'Professional')
        self.assertEqual(schema.benefit_months, 3)
        self.assertIsNone(schema.discount_percent)
        self.assertEqual(schema.status, 'ACTIVE')

    def test_gift_benefit_derives_months_from_window_when_voucher_null(self):
        benefit = SimpleNamespace(
            id=uuid4(),
            voucher_type='GIFT',
            subscription_id=uuid4(),
            subscription=SimpleNamespace(name='Professional'),
            benefit_start='2026-07-11T00:00:00Z',
            benefit_end='2027-07-11T00:00:00Z',
            discount_percent=None,
            remaining_discount_cycles=None,
            status='ACTIVE',
            redemption=SimpleNamespace(
                voucher=SimpleNamespace(
                    serial='WLGX-GFT-FHVKVOI9',
                    benefit_months=None,
                    discount_duration_months=None,
                ),
            ),
        )

        schema = _to_active_benefit_schema(benefit)

        self.assertEqual(schema.benefit_months, 12)
        self.assertEqual(schema.voucher_serial, 'WLGX-GFT-FHVKVOI9')

    def test_discount_benefit_includes_percent_and_cycles(self):
        benefit = SimpleNamespace(
            id=uuid4(),
            voucher_type='DISCOUNT',
            subscription_id=uuid4(),
            subscription=SimpleNamespace(name='Enterprise'),
            benefit_start='2026-07-01T00:00:00Z',
            benefit_end='2026-10-01T00:00:00Z',
            discount_percent=Decimal('20'),
            remaining_discount_cycles=2,
            status='ACTIVE',
            redemption=SimpleNamespace(
                voucher=SimpleNamespace(
                    serial='WLGX-DSC-SHOW01',
                    benefit_months=None,
                    discount_duration_months=3,
                ),
            ),
        )

        schema = _to_active_benefit_schema(benefit)

        self.assertEqual(schema.voucher_type, 'DISCOUNT')
        self.assertEqual(schema.discount_percent, Decimal('20'))
        self.assertEqual(schema.remaining_discount_cycles, 2)
        self.assertEqual(schema.discount_duration_months, 3)
        self.assertIsNone(schema.benefit_months)
