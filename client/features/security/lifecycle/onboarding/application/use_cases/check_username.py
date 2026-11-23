from client.features.security.lifecycle.onboarding.domain.interfaces import ICompanyRegistrationRepository
from core.trace import trace_layer


class CheckUsernameAvailabilityUseCase:
    """Fail-fast username uniqueness probe for the onboarding admin step.

    Only checks persisted users — in-progress registrations that have not
    finalized yet are intentionally ignored (finalize re-checks).
    """

    def __init__(self, repository: ICompanyRegistrationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, username: str) -> bool:
        normalized = username.strip()
        if not normalized:
            return False
        return not self.repository.username_taken(normalized)
