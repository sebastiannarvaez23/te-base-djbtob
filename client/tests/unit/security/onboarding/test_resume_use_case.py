"""Unit tests for ResumeOnboardingUseCase.

Cover the magic-link consumption semantics:
  * rehydrate returns a fresh session token when the resume token is valid
  * the resume token is revoked after honouring (one-shot replay guard)
  * bad / unknown resume tokens produce ONB_007 INVALID_TOKEN
  * completed / expired / missing registrations are rejected with their
    specific codes so the frontend can branch on them
  * the registration ID from the resume token is never trusted blindly —
    the repository is consulted to prove the row still exists

No database, no Redis; repo and token stores are replaced by Mocks.
"""
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

from core.errors import AppErrorCode, OnboardingException
from client.features.security.lifecycle.onboarding.application.use_cases.resume import (
    ResumeOnboardingUseCase,
)


def _registration(status='in_progress', expired=False):
    reg = MagicMock()
    reg.id = uuid4()
    reg.status = status
    reg.is_expired.return_value = expired
    return reg


class TestResumeOnboardingUseCaseHappyPath(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.token_store = MagicMock()
        self.resume_token_store = MagicMock()
        self.use_case = ResumeOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            resume_token_store=self.resume_token_store,
            token_ttl_seconds=7200,
        )

    def test_returns_session_token_and_registration_id_when_resume_token_valid(self):
        reg = _registration()
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg
        self.token_store.issue.return_value = 'new-session-token'

        session_token, registration_id = self.use_case.execute('raw-resume-token')

        self.assertEqual(session_token, 'new-session-token')
        self.assertEqual(registration_id, reg.id)

    def test_session_token_is_issued_with_configured_ttl(self):
        reg = _registration()
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        self.use_case.execute('raw-resume-token')

        self.token_store.issue.assert_called_once_with(reg.id, ttl_seconds=7200)

    def test_resume_token_is_revoked_after_successful_consumption(self):
        """One-shot: the magic-link cannot be replayed after the cookie is issued."""
        reg = _registration()
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        self.use_case.execute('raw-resume-token')

        self.resume_token_store.revoke.assert_called_once_with('raw-resume-token')

    def test_repository_is_consulted_before_issuing_cookie(self):
        """The registration row is the authoritative state — we re-read it."""
        reg = _registration()
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        self.use_case.execute('raw-resume-token')

        self.repo.get.assert_called_once_with(reg.id)


class TestResumeOnboardingUseCaseInvalidToken(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.token_store = MagicMock()
        self.resume_token_store = MagicMock()
        self.use_case = ResumeOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            resume_token_store=self.resume_token_store,
            token_ttl_seconds=7200,
        )

    def test_unknown_token_raises_onb_007(self):
        self.resume_token_store.resolve.return_value = None

        with self.assertRaises(OnboardingException) as ctx:
            self.use_case.execute('never-issued')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_INVALID_TOKEN)

    def test_unknown_token_does_not_call_repository(self):
        self.resume_token_store.resolve.return_value = None

        with self.assertRaises(OnboardingException):
            self.use_case.execute('never-issued')

        self.repo.get.assert_not_called()

    def test_unknown_token_does_not_issue_session(self):
        self.resume_token_store.resolve.return_value = None

        with self.assertRaises(OnboardingException):
            self.use_case.execute('never-issued')

        self.token_store.issue.assert_not_called()

    def test_unknown_token_does_not_revoke(self):
        """Nothing to revoke — avoid masking which path rejected the token."""
        self.resume_token_store.resolve.return_value = None

        with self.assertRaises(OnboardingException):
            self.use_case.execute('never-issued')

        self.resume_token_store.revoke.assert_not_called()


class TestResumeOnboardingUseCaseRegistrationState(TestCase):
    """The resume token might be valid but the underlying registration is not
    consumable any more — each rejection must carry its own error code so the
    frontend can offer a meaningful recovery (start over, sign in, etc.)."""

    def setUp(self):
        self.repo = MagicMock()
        self.token_store = MagicMock()
        self.resume_token_store = MagicMock()
        self.use_case = ResumeOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            resume_token_store=self.resume_token_store,
            token_ttl_seconds=7200,
        )

    def test_missing_registration_raises_onb_001(self):
        self.resume_token_store.resolve.return_value = uuid4()
        self.repo.get.return_value = None

        with self.assertRaises(OnboardingException) as ctx:
            self.use_case.execute('raw-resume-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_NOT_FOUND)

    def test_completed_registration_raises_onb_003(self):
        reg = _registration(status='completed')
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        with self.assertRaises(OnboardingException) as ctx:
            self.use_case.execute('raw-resume-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_ALREADY_COMPLETED)

    def test_expired_registration_raises_onb_002(self):
        reg = _registration(expired=True)
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        with self.assertRaises(OnboardingException) as ctx:
            self.use_case.execute('raw-resume-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_EXPIRED)

    def test_no_session_token_issued_when_registration_completed(self):
        reg = _registration(status='completed')
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        with self.assertRaises(OnboardingException):
            self.use_case.execute('raw-resume-token')

        self.token_store.issue.assert_not_called()

    def test_no_resume_revoke_when_registration_state_rejects(self):
        """Don't burn the token just because the row is in a bad state —
        leave revocation to the successful path only."""
        reg = _registration(status='completed')
        self.resume_token_store.resolve.return_value = reg.id
        self.repo.get.return_value = reg

        with self.assertRaises(OnboardingException):
            self.use_case.execute('raw-resume-token')

        self.resume_token_store.revoke.assert_not_called()


class TestResumeOnboardingUseCaseWiring(TestCase):
    """Contract checks that protect the construction call-site in api.py."""

    def test_constructor_stores_the_ttl(self):
        uc = ResumeOnboardingUseCase(
            repository=MagicMock(),
            token_store=MagicMock(),
            resume_token_store=MagicMock(),
            token_ttl_seconds=3600,
        )
        self.assertEqual(uc.token_ttl, 3600)

    def test_revoke_uses_the_raw_token_not_the_hashed_or_resolved_id(self):
        """A common mistake would be to revoke by registration_id instead of
        by raw token — that would leak other tokens for the same session."""
        repo = MagicMock()
        token_store = MagicMock()
        resume_store = MagicMock()
        reg = _registration()
        resume_store.resolve.return_value = reg.id
        repo.get.return_value = reg

        ResumeOnboardingUseCase(
            repository=repo,
            token_store=token_store,
            resume_token_store=resume_store,
            token_ttl_seconds=900,
        ).execute('exact-raw-token')

        resume_store.revoke.assert_called_once_with('exact-raw-token')
