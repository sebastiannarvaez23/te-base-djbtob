"""Unit tests for StartOnboardingUseCase.

Uniqueness of provisioned users is delegated to
``ICompanyRegistrationRepository.email_taken``.
"""
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from django.db import IntegrityError

from core.errors import AppErrorCode, OnboardingException
from client.features.security.lifecycle.onboarding.application.use_cases.start import (
    StartOnboardingUseCase,
)

pytestmark = pytest.mark.unit


def _registration(email='foo@example.com'):
    reg = MagicMock()
    reg.id = uuid4()
    reg.email = email
    return reg


class TestStartOnboardingUniquenessChecks(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.token_store = MagicMock()
        self.repo.get_active_by_email.return_value = None
        self.repo.email_taken.return_value = False
        self.token_store.issue.return_value = 'session-token'

    def _uc(self):
        return StartOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            registration_ttl_seconds=7 * 86400,
            token_ttl_seconds=7200,
        )

    def test_rejects_when_email_already_belongs_to_a_user(self):
        self.repo.email_taken.return_value = True
        self.repo.create.return_value = _registration()

        with self.assertRaises(OnboardingException) as ctx:
            self._uc().execute(email='owned@example.com')

        self.assertEqual(
            ctx.exception.code,
            AppErrorCode.ONBOARDING_EMAIL_ALREADY_REGISTERED,
        )
        self.repo.create.assert_not_called()
        self.repo.get_active_by_email.assert_not_called()

    def test_email_check_delegates_raw_email_to_port(self):
        self.repo.create.return_value = _registration()
        self._uc().execute(email='Mixed.Case@Example.COM')
        self.repo.email_taken.assert_called_once_with('Mixed.Case@Example.COM')

    def test_creates_registration_when_no_active_duplicate(self):
        reg = _registration()
        self.repo.create.return_value = reg

        token, returned = self._uc().execute(email='foo@example.com')

        self.assertEqual(token, 'session-token')
        self.assertEqual(returned, reg)
        self.repo.create.assert_called_once_with(
            email='foo@example.com', ttl_seconds=7 * 86400,
        )

    def test_raises_when_active_registration_already_exists(self):
        self.repo.get_active_by_email.return_value = _registration()

        with self.assertRaises(OnboardingException) as ctx:
            self._uc().execute(email='foo@example.com')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)
        self.repo.create.assert_not_called()

    def test_race_on_partial_unique_index_maps_to_duplicate_email(self):
        self.repo.create.side_effect = IntegrityError(
            'duplicate key value violates unique constraint "uniq_active_onboarding_email"'
        )

        with self.assertRaises(OnboardingException) as ctx:
            self._uc().execute(email='foo@example.com')

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)

    def test_unrelated_integrity_error_is_propagated(self):
        self.repo.create.side_effect = IntegrityError('something else exploded')

        with self.assertRaises(IntegrityError):
            self._uc().execute(email='foo@example.com')


class TestStartOnboardingMagicLinkDispatch(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.token_store = MagicMock()
        self.resume_store = MagicMock()
        self.dispatcher = MagicMock()
        self.repo.get_active_by_email.return_value = None
        self.repo.email_taken.return_value = False
        self.reg = _registration(email='user@example.com')
        self.repo.create.return_value = self.reg
        self.token_store.issue.return_value = 'session-token'
        self.resume_store.issue.return_value = 'resume-raw-token'

    def _uc(self):
        return StartOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            registration_ttl_seconds=7 * 86400,
            token_ttl_seconds=7200,
            resume_token_store=self.resume_store,
            resume_dispatcher=self.dispatcher,
        )

    def test_resume_token_is_issued_with_registration_ttl_not_session_ttl(self):
        self._uc().execute(email='user@example.com')
        self.resume_store.issue.assert_called_once_with(
            self.reg.id, ttl_seconds=7 * 86400,
        )

    def test_dispatcher_receives_email_raw_token_and_ttl(self):
        self._uc().execute(email='user@example.com')
        self.dispatcher.assert_called_once_with(
            'user@example.com', 'resume-raw-token', 7 * 86400,
        )

    def test_dispatcher_exception_does_not_break_start(self):
        self.dispatcher.side_effect = RuntimeError('smtp down')
        token, reg = self._uc().execute(email='user@example.com')
        self.assertEqual(token, 'session-token')
        self.assertEqual(reg, self.reg)

    def test_dispatcher_skipped_when_resume_store_missing(self):
        uc = StartOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            registration_ttl_seconds=7 * 86400,
            token_ttl_seconds=7200,
            resume_token_store=None,
            resume_dispatcher=self.dispatcher,
        )
        uc.execute(email='user@example.com')
        self.dispatcher.assert_not_called()

    def test_dispatcher_skipped_when_dispatcher_missing(self):
        uc = StartOnboardingUseCase(
            repository=self.repo,
            token_store=self.token_store,
            registration_ttl_seconds=7 * 86400,
            token_ttl_seconds=7200,
            resume_token_store=self.resume_store,
            resume_dispatcher=None,
        )
        uc.execute(email='user@example.com')
        self.resume_store.issue.assert_not_called()
