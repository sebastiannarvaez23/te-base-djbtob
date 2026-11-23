"""
StepResolver
────────────
Pure function that derives the *current step* of an onboarding from a
state snapshot. No I/O, no side effects — trivially unit-testable.

The resolver is the single source of truth for step ordering:
views, serializers and clients must NEVER infer the step themselves.
"""

from dataclasses import dataclass

from ..domain.enums import OnboardingStep


@dataclass(frozen=True)
class StepState:
    company_data_completed: bool
    admin_user_completed: bool
    subscription_selected: bool
    payment_completed: bool
    requires_payment: bool


class StepResolver:

    @staticmethod
    def resolve(state: StepState) -> OnboardingStep:
        if not state.company_data_completed:
            return OnboardingStep.COMPANY
        if not state.admin_user_completed:
            return OnboardingStep.ADMIN_USER
        if not state.subscription_selected:
            return OnboardingStep.SUBSCRIPTION
        if state.requires_payment and not state.payment_completed:
            return OnboardingStep.PAYMENT
        return OnboardingStep.CONFIRMATION

    @staticmethod
    def assert_step_matches(state: StepState, requested: OnboardingStep) -> bool:
        """Guard: reject writes that don't target the current canonical step.

        Writes to *earlier* steps are allowed (user editing data), but
        writes to *later* steps are not (client out of sync).
        """
        current = StepResolver.resolve(state)
        order = [
            OnboardingStep.COMPANY,
            OnboardingStep.ADMIN_USER,
            OnboardingStep.SUBSCRIPTION,
            OnboardingStep.PAYMENT,
            OnboardingStep.CONFIRMATION,
        ]
        return order.index(requested) <= order.index(current)
