"""Unit tests for ResendOnboardingResumeLinkUseCase.

The use case has three responsibilities:

  1. Find the in-progress registration for the given email.
  2. Throttle: at most one resend per email within ``ONB_RESUME_WND_S``.
  3. Issue a fresh resume token and dispatch the magic-link email.

Collaborators are injected (including ``IResumeLinkThrottle``).
"""
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, OnboardingException
from client.features.security.lifecycle.onboarding.application.use_cases.resend_resume_link import (
    ResendOnboardingResumeLinkUseCase,
)

pytestmark = pytest.mark.unit


_TTL_SECONDS = 7 * 86400


def _registration(email='abandoned@example.com'):
    reg = MagicMock()
    reg.id = uuid4()
    reg.email = email
    return reg


def _open_throttle():
    throttle = MagicMock()
    throttle.try_acquire.return_value = True
    throttle.retry_after.return_value = None
    return throttle


def _make_uc(repo, resume_store, dispatcher, throttle=None):
    return ResendOnboardingResumeLinkUseCase(
        repository=repo,
        resume_token_store=resume_store,
        resume_dispatcher=dispatcher,
        registration_ttl_seconds=_TTL_SECONDS,
        throttle=throttle if throttle is not None else _open_throttle(),
    )


class TestResendResumeLinkLookup(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.resume_store = MagicMock()
        self.dispatcher = MagicMock()
        self.throttle = _open_throttle()

    def test_no_active_registration_raises_not_found(self):
        self.repo.get_active_by_email.return_value = None

        with self.assertRaises(OnboardingException) as ctx:
            _make_uc(
                self.repo, self.resume_store, self.dispatcher, self.throttle,
            ).execute(email='unknown@example.com')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_NOT_FOUND)
        self.throttle.try_acquire.assert_not_called()
        self.resume_store.issue.assert_not_called()
        self.dispatcher.assert_not_called()


class TestResendResumeLinkThrottle(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.resume_store = MagicMock()
        self.dispatcher = MagicMock()
        self.repo.get_active_by_email.return_value = _registration()
        self.resume_store.issue.return_value = 'fresh-resume-token'
        self.throttle = _open_throttle()

    def test_throttled_call_raises_resend_throttled(self):
        self.throttle.try_acquire.return_value = False
        self.throttle.retry_after.return_value = 17

        with self.assertRaises(OnboardingException) as ctx:
            _make_uc(
                self.repo, self.resume_store, self.dispatcher, self.throttle,
            ).execute(email='abandoned@example.com')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_RESEND_THROTTLED)
        self.assertEqual(ctx.exception.retry_after, 17)
        self.resume_store.issue.assert_not_called()
        self.dispatcher.assert_not_called()

    def test_acquired_slot_issues_token_and_dispatches(self):
        _make_uc(
            self.repo, self.resume_store, self.dispatcher, self.throttle,
        ).execute(email='abandoned@example.com')

        self.resume_store.issue.assert_called_once()
        call = self.resume_store.issue.call_args
        self.assertEqual(call.kwargs['ttl_seconds'], _TTL_SECONDS)

        self.dispatcher.assert_called_once_with(
            'abandoned@example.com', 'fresh-resume-token', _TTL_SECONDS,
        )


class TestResendResumeLinkDispatchFailure(TestCase):

    def test_dispatcher_exception_maps_to_server_error(self):
        repo = MagicMock()
        resume_store = MagicMock()
        dispatcher = MagicMock(side_effect=RuntimeError('smtp down'))
        repo.get_active_by_email.return_value = _registration()
        resume_store.issue.return_value = 'fresh-resume-token'

        with self.assertRaises(OnboardingException) as ctx:
            _make_uc(repo, resume_store, dispatcher).execute(
                email='abandoned@example.com',
            )

        self.assertEqual(ctx.exception.code, AppErrorCode.SERVER_ERROR)


class TestResendResumeLinkIntegrationOrdering(TestCase):

    def test_throttle_check_runs_before_token_issuance(self):
        repo = MagicMock()
        resume_store = MagicMock()
        dispatcher = MagicMock()
        throttle = _open_throttle()
        throttle.try_acquire.return_value = False
        repo.get_active_by_email.return_value = _registration()

        with self.assertRaises(OnboardingException):
            _make_uc(repo, resume_store, dispatcher, throttle).execute(
                email='abandoned@example.com',
            )

        throttle.try_acquire.assert_called_once_with('abandoned@example.com')
        resume_store.issue.assert_not_called()
