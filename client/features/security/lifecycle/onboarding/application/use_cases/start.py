import logging
from typing import Callable, Optional

from django.db import IntegrityError

from core.errors import AppErrorCode, OnboardingException

from ...domain.interfaces import (
    ICompanyRegistrationRepository,
    IOnboardingResumeTokenStore,
    IOnboardingTokenStore,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class StartOnboardingUseCase:
    """Create a fresh onboarding or reject if an active one exists for this email.

    Resume-by-email is handled via a separate magic-link endpoint that
    consumes the resume-token issued (and emailed) here.
    """

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        token_store: IOnboardingTokenStore,
        registration_ttl_seconds: int,
        token_ttl_seconds: int,
        resume_token_store: Optional[IOnboardingResumeTokenStore] = None,
        resume_dispatcher: Optional[Callable[[str, str, int], None]] = None,
    ):
        self.repository = repository
        self.token_store = token_store
        self.registration_ttl = registration_ttl_seconds
        self.token_ttl = token_ttl_seconds
        self.resume_token_store = resume_token_store
        self.resume_dispatcher = resume_dispatcher

    @trace_layer('application')
    def execute(self, email: str) -> tuple[str, "CompanyRegistrationOrm"]:  # noqa: F821
        # Reject if a fully-provisioned account already owns this email.
        # The check is case-insensitive (repository uses email__iexact).
        if self.repository.email_taken(email):
            raise OnboardingException(AppErrorCode.ONBOARDING_EMAIL_ALREADY_REGISTERED)

        existing = self.repository.get_active_by_email(email)
        if existing is not None:
            raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)

        try:
            reg = self.repository.create(email=email, ttl_seconds=self.registration_ttl)
        except IntegrityError as exc:
            # Concurrent request beat us to the partial unique index on (email, in_progress).
            if 'uniq_active_onboarding_email' in str(exc).lower():
                raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_EMAIL) from exc
            raise

        token = self.token_store.issue(reg.id, ttl_seconds=self.token_ttl)

        # Best-effort: emit the magic-link so the user can resume from email.
        if self.resume_token_store is not None and self.resume_dispatcher is not None:
            try:
                resume_raw = self.resume_token_store.issue(
                    reg.id, ttl_seconds=self.registration_ttl,
                )
                self.resume_dispatcher(reg.email, resume_raw, self.registration_ttl)
            except Exception:
                logger.exception('Resume-link dispatch failed for email=%s', email)

        return token, reg
