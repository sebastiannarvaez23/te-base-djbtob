from uuid import UUID

from core.errors import AppErrorCode, OnboardingException

from ...domain.interfaces import ICompanyRegistrationRepository
from ...domain.schemas import OnboardingStateSchema
from ._common import build_state_schema
from core.trace import trace_layer


class GetOnboardingStateUseCase:

    def __init__(self, repository: ICompanyRegistrationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, registration_id: UUID) -> OnboardingStateSchema:
        reg = self.repository.get(registration_id)
        if reg is None:
            raise OnboardingException(AppErrorCode.ONBOARDING_NOT_FOUND)
        return build_state_schema(reg)
