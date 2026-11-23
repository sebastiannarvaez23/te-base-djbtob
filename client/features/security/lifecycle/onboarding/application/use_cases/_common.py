"""Shared helpers used across onboarding use cases."""

from core.errors import AppErrorCode, OnboardingException

from ...domain.enums import OnboardingStatus, OnboardingStep
from ...domain.schemas import OnboardingStateSchema
from ..step_resolver import StepResolver, StepState


def build_step_state(reg) -> StepState:
    return StepState(
        company_data_completed=reg.company_data_completed,
        admin_user_completed=reg.admin_user_completed,
        subscription_selected=reg.subscription_selected,
        payment_completed=reg.payment_completed,
        requires_payment=reg.requires_payment,
    )


_ADMIN_USER_PUBLIC_KEYS = (
    'email',
    'username',
    'telephone',
    'phone_country_code',
    'first_name',
    'second_name',
    'last_name',
    'second_last_name',
    'document_type',
    'document_number',
    'birth_date',
)
_PAYMENT_PUBLIC_KEYS    = ('holder', 'last4', 'expiry_month', 'expiry_year')


def _safe_subset(payload: dict | None, allowed: tuple[str, ...]) -> dict:
    """Return a shallow copy of ``payload`` containing only ``allowed`` keys.

    Used to scrub sensitive fields (password_hash, processor_token) before
    they leave the use-case layer.
    """
    if not payload:
        return {}
    return {k: payload[k] for k in allowed if k in payload}


def build_state_schema(reg) -> OnboardingStateSchema:
    """Project a CompanyRegistration ORM instance into the public state schema.

    Sensitive fields are stripped here (never sent to the client):
      - admin_user_data: ``password_hash`` is removed.
      - payment_data:    ``processor_token`` is removed.

    The remaining values let the frontend pre-fill wizard forms after a
    resume so the user only re-enters fields they cannot see (password,
    full PAN, CVV).
    """
    current_step = StepResolver.resolve(build_step_state(reg))
    admin_user_data = reg.admin_user_data or {}
    return OnboardingStateSchema(
        id=reg.id,
        status=reg.status,
        current_step=current_step.value,
        email=reg.email,
        nit=reg.nit,
        schema_name=reg.schema_name,
        company_data_completed=reg.company_data_completed,
        admin_user_completed=reg.admin_user_completed,
        subscription_selected=reg.subscription_selected,
        payment_completed=reg.payment_completed,
        admin_user_password_set=bool(admin_user_data.get('password_hash')),
        requires_payment=reg.requires_payment,
        subscription_id=reg.subscription_id,
        company_data=reg.company_data or {},
        subscription_data=reg.subscription_data or {},
        admin_user_data=_safe_subset(admin_user_data, _ADMIN_USER_PUBLIC_KEYS),
        payment_data=_safe_subset(reg.payment_data, _PAYMENT_PUBLIC_KEYS),
        expires_at=reg.expires_at.isoformat(),
    )


def ensure_active(reg) -> None:
    """Validate that the registration can still be written to."""
    if reg is None:
        raise OnboardingException(AppErrorCode.ONBOARDING_NOT_FOUND)
    if reg.status == OnboardingStatus.COMPLETED.value:
        raise OnboardingException(AppErrorCode.ONBOARDING_ALREADY_COMPLETED)
    if reg.status == OnboardingStatus.EXPIRED.value or reg.is_expired():
        raise OnboardingException(AppErrorCode.ONBOARDING_EXPIRED)


def ensure_step_writable(reg, requested: OnboardingStep) -> None:
    """Reject out-of-order writes.

    Re-writing an already-completed prior step is allowed (user editing);
    writing to a step beyond the current canonical position is not.
    """
    state = build_step_state(reg)
    if not StepResolver.assert_step_matches(state, requested):
        raise OnboardingException(AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER)
