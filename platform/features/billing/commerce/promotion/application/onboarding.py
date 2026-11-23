"""Onboarding promotion validate/apply use cases.

Ports are required — wire them in ``composition.py`` / presentation.
"""

from uuid import UUID

from core.errors import AppErrorCode, AppException, OnboardingException

from client.features.security.lifecycle.onboarding.application.use_cases._common import (
    build_state_schema,
    ensure_active,
)

from ..domain.interfaces import IOnboardingRegistrationPort
from ..domain.schemas import ValidateVoucherSchema
from core.trace import trace_layer


def _assert_registration_subscription(reg, subscription_id: UUID) -> None:
    if not reg.subscription_selected or reg.subscription_id is None:
        raise OnboardingException(AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER)
    if reg.subscription_id != subscription_id:
        raise AppException(AppErrorCode.PROMO_INCOMPATIBLE)


def _resolve_billing_interval(reg, billing_interval: str | None) -> str | None:
    """Prefer explicit arg; else registration payload. Ignore non-string junk."""
    if isinstance(billing_interval, str) and billing_interval.strip():
        return billing_interval.strip()
    data = getattr(reg, 'subscription_data', None)
    if isinstance(data, dict):
        value = data.get('billing_interval')
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class ValidateOnboardingPromotionUseCase:
    def __init__(self, *, registration: IOnboardingRegistrationPort, validate_use_case):
        self._reg = registration
        self._validate = validate_use_case

    @trace_layer('application')
    def execute(
        self,
        registration_id: UUID,
        *,
        serial: str,
        subscription_id: UUID,
        billing_interval: str | None = None,
    ):
        reg = self._reg.get(registration_id)
        ensure_active(reg)
        _assert_registration_subscription(reg, subscription_id)
        interval = _resolve_billing_interval(reg, billing_interval)
        return self._validate.execute(
            ValidateVoucherSchema(
                serial=serial,
                subscription_id=subscription_id,
                company_id=None,
                context='ONBOARDING',
                billing_interval=interval,
            )
        )


class ApplyOnboardingPromotionUseCase:
    def __init__(self, *, registration: IOnboardingRegistrationPort, validate_use_case):
        self._reg = registration
        self._validate = validate_use_case

    @trace_layer('application')
    def execute(
        self,
        registration_id: UUID,
        *,
        serial: str,
        subscription_id: UUID,
        billing_interval: str | None = None,
    ):
        reg = self._reg.get(registration_id)
        ensure_active(reg)
        _assert_registration_subscription(reg, subscription_id)

        interval = _resolve_billing_interval(reg, billing_interval)
        preview = self._validate.execute(
            ValidateVoucherSchema(
                serial=serial,
                subscription_id=subscription_id,
                company_id=None,
                context='ONBOARDING',
                billing_interval=interval,
            )
        )
        self._reg.save_promotion_apply(
            registration_id,
            serial=serial,
            promotion_preview=preview.model_dump(mode='json'),
        )
        reg = self._reg.get(registration_id)
        return build_state_schema(reg)
