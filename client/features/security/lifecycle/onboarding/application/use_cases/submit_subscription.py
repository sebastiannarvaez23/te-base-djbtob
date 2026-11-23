from uuid import UUID

from core.errors import AppErrorCode, OnboardingException

from ...domain.enums import OnboardingStep
from ...domain.interfaces import ICompanyRegistrationRepository, IOnboardingPlanCatalog
from ...domain.schemas import OnboardingStateSchema, SubscriptionStepSchema
from ._common import build_state_schema, ensure_active, ensure_step_writable
from core.trace import trace_layer


class SubmitSubscriptionStepUseCase:

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        plan_catalog: IOnboardingPlanCatalog,
    ):
        self.repository = repository
        self.plan_catalog = plan_catalog

    @trace_layer('application')
    def execute(self, registration_id: UUID, data: SubscriptionStepSchema) -> OnboardingStateSchema:
        reg = self.repository.get(registration_id)
        ensure_active(reg)
        ensure_step_writable(reg, OnboardingStep.SUBSCRIPTION)

        from platform.features.billing.subscription.subscription.domain.billing_cycle import (
            charge_amount,
            normalize_billing_interval,
            yearly_amount,
        )

        sub = self.plan_catalog.get_active_plan(data.subscription_id)
        if sub is None:
            raise OnboardingException(AppErrorCode.ONBOARDING_INVALID_PLAN)

        interval = normalize_billing_interval(data.billing_interval)
        percent = self.plan_catalog.annual_discount_percent()
        cycle_amount = charge_amount(sub.price, interval, percent)
        requires_payment = cycle_amount > 0
        # Persisted enriched so the frontend can rehydrate the wizard
        # (name + price) on resume without an extra catalog fetch.
        # Plan change clears any previously applied promotion.
        subscription_payload = {
            'subscription_id': str(data.subscription_id),
            'name': sub.name,
            'price': float(sub.price),
            'currency': (str(getattr(sub, 'currency', None) or 'USD').strip().upper() or 'USD'),
            'yearly_price': float(yearly_amount(sub.price, percent)),
            'billing_interval': interval,
            'charge_amount': float(cycle_amount),
        }
        # The repository invalidates payment_completed when requires_payment flips.
        self.repository.save_subscription_step(
            registration_id, data,
            requires_payment=requires_payment,
            subscription_payload=subscription_payload,
        )

        # Mirror locally: replicate the same invalidation logic so the
        # returned state matches what was persisted.
        if reg.requires_payment != requires_payment:
            reg.payment_completed = False
            reg.payment_data = {}
        reg.subscription_id = data.subscription_id
        reg.subscription_data = subscription_payload
        reg.subscription_selected = True
        reg.requires_payment = requires_payment
        return build_state_schema(reg)
