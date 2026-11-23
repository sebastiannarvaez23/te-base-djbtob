"""Consume a magic-link resume token and rehydrate an onboarding session.

The resume token is one-shot from a security standpoint: we revoke it
after issuing the short-lived session token. The user's *registration
row* in PostgreSQL is the authoritative state — the resume token is
just a handle that proves "you own this email".
"""

from uuid import UUID

from core.errors import AppErrorCode, OnboardingException

from ...domain.interfaces import (
    ICompanyRegistrationRepository,
    IOnboardingResumeTokenStore,
    IOnboardingTokenStore,
)
from core.trace import trace_layer


class ResumeOnboardingUseCase:

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        token_store: IOnboardingTokenStore,
        resume_token_store: IOnboardingResumeTokenStore,
        token_ttl_seconds: int,
    ):
        self.repository = repository
        self.token_store = token_store
        self.resume_token_store = resume_token_store
        self.token_ttl = token_ttl_seconds

    @trace_layer('application')
    def execute(self, raw_token: str) -> tuple[str, UUID]:
        registration_id = self.resume_token_store.resolve(raw_token)
        if registration_id is None:
            raise OnboardingException(AppErrorCode.ONBOARDING_INVALID_TOKEN)

        reg = self.repository.get(registration_id)
        if reg is None:
            raise OnboardingException(AppErrorCode.ONBOARDING_NOT_FOUND)
        if reg.status != 'in_progress':
            raise OnboardingException(AppErrorCode.ONBOARDING_ALREADY_COMPLETED)
        if reg.is_expired():
            raise OnboardingException(AppErrorCode.ONBOARDING_EXPIRED)

        # One-shot: invalidate the magic-link as soon as it's been honoured
        # so a leaked email link can't keep being replayed.
        self.resume_token_store.revoke(raw_token)

        session_token = self.token_store.issue(
            registration_id, ttl_seconds=self.token_ttl,
        )
        return session_token, registration_id
