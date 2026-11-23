"""Re-issue the onboarding magic-link for an in-progress registration.

Lets a user who already started onboarding (and lost the email or whose
session cookie expired) request a new magic-link by re-entering the same
email at /start/'s resend CTA. Throttled per email to keep this from
being a spam vector.

Security note: this endpoint is intentionally non-revealing. To callers
that pass an email *without* an active registration, the use case raises
``ONBOARDING_NOT_FOUND``; the API view should map that into the same
generic response shape so an attacker cannot enumerate which emails are
mid-onboarding by polling this endpoint.

Re-issuing the resume token revokes prior issuances implicitly via the
short Redis TTL — the previous magic-link in the user's inbox might
still work until its own TTL expires; this is acceptable because both
tokens point to the same registration_id.
"""

import logging
from typing import Callable

from core.errors import AppErrorCode, OnboardingException

from ...domain.interfaces import (
    ICompanyRegistrationRepository,
    IOnboardingResumeTokenStore,
    IResumeLinkThrottle,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class ResendOnboardingResumeLinkUseCase:

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        resume_token_store: IOnboardingResumeTokenStore,
        resume_dispatcher: Callable[[str, str, int], None],
        registration_ttl_seconds: int,
        throttle: IResumeLinkThrottle,
    ):
        self.repository = repository
        self.resume_token_store = resume_token_store
        self.resume_dispatcher = resume_dispatcher
        self.registration_ttl = registration_ttl_seconds
        self.throttle = throttle

    @trace_layer('application')
    def execute(self, email: str) -> None:
        reg = self.repository.get_active_by_email(email)
        if reg is None:
            # No active onboarding for that email. Don't reveal whether
            # the email is/was registered — the view layer maps this to
            # the same UX as a successful resend.
            raise OnboardingException(AppErrorCode.ONBOARDING_NOT_FOUND)

        if not self.throttle.try_acquire(email):
            raise OnboardingException(
                AppErrorCode.ONBOARDING_RESEND_THROTTLED,
                retry_after=self.throttle.retry_after(email),
            )

        try:
            raw = self.resume_token_store.issue(reg.id, ttl_seconds=self.registration_ttl)
            self.resume_dispatcher(reg.email, raw, self.registration_ttl)
        except OnboardingException:
            raise
        except Exception:
            logger.exception(
                'Resume-link resend failed for email=%s', email,
            )
            # Swallow infra failures: never block the user from retrying
            # within the next throttle window.
            raise OnboardingException(AppErrorCode.SERVER_ERROR)
