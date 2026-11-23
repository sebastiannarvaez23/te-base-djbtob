from uuid import UUID

from core.errors import AppErrorCode, OnboardingException

from ...domain.enums import OnboardingStep
from ...domain.interfaces import ICompanyRegistrationRepository
from ...domain.schemas import OnboardingStateSchema, PaymentStepSchema
from ._common import build_state_schema, ensure_active, ensure_step_writable
from core.trace import trace_layer


class SubmitPaymentStepUseCase:

    def __init__(self, repository: ICompanyRegistrationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, registration_id: UUID, data: PaymentStepSchema) -> OnboardingStateSchema:
        reg = self.repository.get(registration_id)
        ensure_active(reg)
        ensure_step_writable(reg, OnboardingStep.PAYMENT)

        if not reg.requires_payment:
            # Free plan: posting payment is a client bug, block it.
            raise OnboardingException(
                AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER,
                override_detail='The selected plan does not require a payment method.',
            )
        self.repository.save_payment_step(registration_id, data)

        reg.payment_completed = True
        return build_state_schema(reg)
