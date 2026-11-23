"""Unit tests for SubmitSubscriptionStepUseCase.

The use case has three behaviours we care about:

  1. Reject unknown / inactive plans with ONB_009.
  2. Persist a subscription_payload **with name + price** (not just the
     id) so the frontend can rehydrate the wizard on resume without a
     catalog roundtrip.
  3. Compute ``requires_payment`` from the plan price and forward it to
     the repository so the latter can invalidate stale payment data
     when the user switches between paid and free plans.

Mocks the repository and plan catalog port so the suite runs without DB.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4
from decimal import Decimal

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from core.errors import AppErrorCode, OnboardingException

from client.features.security.lifecycle.onboarding.application.use_cases.submit_subscription import (
    SubmitSubscriptionStepUseCase,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
    OnboardingStep,
)
from client.features.security.lifecycle.onboarding.domain.interfaces import IOnboardingPlanCatalog
from client.features.security.lifecycle.onboarding.domain.schemas import (
    OnboardingPlanQuote,
    SubscriptionStepSchema,
)

RESOLVER_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '._common.StepResolver.resolve'
)


def _orm_stub(**overrides):
    base = dict(
        id=uuid4(),
        status=OnboardingStatus.IN_PROGRESS.value,
        email='founder@example.com',
        nit='900123',
        schema_name='acme',
        company_data_completed=True,
        admin_user_completed=True,
        subscription_selected=False,
        payment_completed=False,
        requires_payment=False,
        subscription_id=None,
        company_data={},
        subscription_data={},
        admin_user_data={},
        payment_data={},
        expires_at=MagicMock(isoformat=lambda: '2026-05-05T00:00:00+00:00'),
    )
    base.update(overrides)
    reg = MagicMock()
    for k, v in base.items():
        setattr(reg, k, v)
    reg.is_expired = lambda: False
    return reg


class _FakeCatalog(IOnboardingPlanCatalog):
    def __init__(self, plan: OnboardingPlanQuote | None = None, percent: Decimal = Decimal('15')):
        self._plan = plan
        self._percent = percent

    def get_active_plan(self, subscription_id):
        return self._plan

    def annual_discount_percent(self):
        return self._percent


class TestSubmitSubscriptionStep(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.reg = _orm_stub()
        self.repo.get.return_value = self.reg
        resolver_patch = patch(RESOLVER_PATH, return_value=OnboardingStep.PAYMENT)
        resolver_patch.start()
        self.addCleanup(resolver_patch.stop)

    def _data(self, sub_id=None, billing_interval='monthly'):
        return SubscriptionStepSchema(
            subscription_id=sub_id or uuid4(),
            billing_interval=billing_interval,
        )

    def _quote(self, plan_id=None, name='Pro', price='49', currency='USD'):
        return OnboardingPlanQuote(
            id=plan_id or uuid4(),
            name=name,
            price=Decimal(str(price)),
            currency=currency,
        )

    def test_unknown_plan_raises_invalid_plan(self):
        uc = SubmitSubscriptionStepUseCase(self.repo, _FakeCatalog(None))
        with self.assertRaises(OnboardingException) as ctx:
            uc.execute(self.reg.id, self._data())

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_INVALID_PLAN)
        self.repo.save_subscription_step.assert_not_called()

    def test_payload_includes_name_and_price(self):
        plan_id = UUID('00000000-0000-0000-0000-0000000000a1')
        catalog = _FakeCatalog(self._quote(plan_id, 'Pro', '49'))

        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(
            self.reg.id, self._data(plan_id),
        )

        self.repo.save_subscription_step.assert_called_once()
        payload = self.repo.save_subscription_step.call_args.kwargs['subscription_payload']
        self.assertEqual(payload['subscription_id'], str(plan_id))
        self.assertEqual(payload['name'], 'Pro')
        self.assertEqual(payload['price'], 49.0)
        self.assertEqual(payload['currency'], 'USD')
        self.assertEqual(payload['billing_interval'], 'monthly')
        self.assertEqual(payload['charge_amount'], 49.0)

    def test_payload_yearly_includes_discounted_charge_amount(self):
        plan_id = UUID('00000000-0000-0000-0000-0000000000a1')
        catalog = _FakeCatalog(self._quote(plan_id, 'Pro', '100'))
        data = self._data(plan_id, billing_interval='yearly')

        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(self.reg.id, data)

        payload = self.repo.save_subscription_step.call_args.kwargs['subscription_payload']
        self.assertEqual(payload['billing_interval'], 'yearly')
        self.assertEqual(payload['yearly_price'], 1020.0)
        self.assertEqual(payload['charge_amount'], 1020.0)

    def test_requires_payment_is_true_for_priced_plans(self):
        catalog = _FakeCatalog(self._quote(name='Standard', price='10'))
        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(
            self.reg.id, self._data(),
        )
        self.assertTrue(self.repo.save_subscription_step.call_args.kwargs['requires_payment'])

    def test_requires_payment_is_false_for_free_plans(self):
        catalog = _FakeCatalog(self._quote(name='Free', price='0'))
        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(
            self.reg.id, self._data(),
        )
        self.assertFalse(self.repo.save_subscription_step.call_args.kwargs['requires_payment'])

    def test_local_mirror_invalidates_payment_when_paid_to_free(self):
        self.reg.requires_payment = True
        self.reg.payment_completed = True
        self.reg.payment_data = {
            'holder': 'X', 'last4': '1234', 'expiry_month': 1, 'expiry_year': 2030,
        }
        catalog = _FakeCatalog(self._quote(name='Free', price='0'))
        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(
            self.reg.id, self._data(),
        )
        self.assertFalse(self.reg.payment_completed)
        self.assertEqual(self.reg.payment_data, {})

    def test_subscription_data_is_set_on_local_mirror(self):
        plan_id = UUID('00000000-0000-0000-0000-0000000000ee')
        catalog = _FakeCatalog(self._quote(plan_id, 'Enterprise', '99'))
        SubmitSubscriptionStepUseCase(self.repo, catalog).execute(
            self.reg.id, self._data(plan_id),
        )
        self.assertEqual(self.reg.subscription_data['subscription_id'], str(plan_id))
        self.assertEqual(self.reg.subscription_data['name'], 'Enterprise')
        self.assertEqual(self.reg.subscription_data['price'], 99.0)
        self.assertTrue(self.reg.subscription_selected)
