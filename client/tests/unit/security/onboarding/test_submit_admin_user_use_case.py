"""Unit tests for SubmitAdminUserStepUseCase.

The use case must support three password paths so the user can re-edit
the admin step (e.g. fix a typo in the username) without having to retype
the password every time:

  1. First submit — password missing → 400 (no hash on file yet).
  2. First submit — password present → validate, hash, persist.
  3. Re-edit     — password missing AND prior hash exists → keep old hash.
  4. Re-edit     — password present → validate, hash, replace.

Mocks the repository and the User model so the suite runs without DB or
auth machinery beyond Django settings.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import pytest

from core.errors import (
    AppErrorCode,
    OnboardingException,
    ValidationAppException,
)

from client.features.security.lifecycle.onboarding.application.use_cases.submit_admin_user import (
    SubmitAdminUserStepUseCase,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
    OnboardingStep,
)
from client.features.security.lifecycle.onboarding.domain.schemas import AdminUserStepSchema

pytestmark = pytest.mark.unit

RESOLVER_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '._common.StepResolver.resolve'
)
HASH_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.submit_admin_user.make_password'
)
VALIDATE_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.submit_admin_user.validate_password'
)


def _orm_stub(**overrides):
    base = dict(
        id=uuid4(),
        status=OnboardingStatus.IN_PROGRESS.value,
        email='founder@example.com',
        nit='900123',
        schema_name='acme',
        company_data_completed=True,
        admin_user_completed=False,
        subscription_selected=False,
        payment_completed=False,
        requires_payment=False,
        subscription_id=None,
        company_data={},
        subscription_data={},
        admin_user_data={},
        payment_data={},
        expires_at=MagicMock(isoformat=lambda: '2026-05-05T00:00:00+00:00'),
    )
    base.update(overrides)
    reg = MagicMock()
    for k, v in base.items():
        setattr(reg, k, v)
    reg.is_expired = lambda: False
    return reg


def _data(**overrides):
    base = dict(
        email='owner@example.com',
        username='owner1',
        telephone='3001234567',
        phone_country_code='CO',
        password='supersecret1',
        password_confirmation='supersecret1',
        first_name='Jane',
        second_name='Ann',
        last_name='Doe',
        second_last_name='Smith',
        document_type='CC',
        document_number='1234567890',
        birth_date='1990-05-15',
    )
    base.update(overrides)
    return AdminUserStepSchema(**base)


class _UseCaseTestBase(TestCase):
    """Shared scaffolding: repo + resolver + User model patched.

    Subclasses set up ``self.reg`` (the ORM stub returned by repo.get) to
    reflect the scenario under test.
    """

    def setUp(self):
        self.repo = MagicMock()
        self.repo.username_taken.return_value = False
        self.repo.email_taken.return_value = False

        resolver_patch = patch(RESOLVER_PATH, return_value=OnboardingStep.SUBSCRIPTION)
        resolver_patch.start()
        self.addCleanup(resolver_patch.stop)

    def _execute(self, schema):
        self.repo.get.return_value = self.reg
        uc = SubmitAdminUserStepUseCase(self.repo)
        return uc.execute(self.reg.id, schema)


class TestPasswordRequiredOnFirstSubmit(_UseCaseTestBase):
    """Step has never been completed → password must be provided."""

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(admin_user_data={})

    def test_missing_password_raises_validation_error(self):
        """Empty password + no stored hash is the user's first submit and
        must fail loudly so they never end up with a no-password admin."""
        with self.assertRaises(ValidationAppException) as ctx:
            self._execute(_data(password='', password_confirmation=''))

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)
        self.repo.save_admin_user_step.assert_not_called()

    def test_missing_password_does_not_query_user_uniqueness(self):
        """Fail-fast: we shouldn't burn DB cycles checking username/email
        uniqueness when the request is already invalid on its face."""
        with self.assertRaises(ValidationAppException):
            self._execute(_data(password='', password_confirmation=''))

        self.repo.username_taken.assert_not_called()
        self.repo.email_taken.assert_not_called()


class TestPasswordPresentOnFirstSubmit(_UseCaseTestBase):
    """Happy path on the first run."""

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(admin_user_data={})

    def test_password_is_validated_and_hashed(self):
        with patch(HASH_PATH, return_value='hashed-pwd') as make_pwd, \
             patch(VALIDATE_PATH) as validate_pwd:
            self._execute(_data())

        validate_pwd.assert_called_once_with('supersecret1')
        make_pwd.assert_called_once_with('supersecret1')
        self.repo.save_admin_user_step.assert_called_once()
        kwargs = self.repo.save_admin_user_step.call_args.kwargs
        self.assertEqual(kwargs['hashed_password'], 'hashed-pwd')

    def test_mismatched_passwords_raise_validation_error(self):
        with self.assertRaises(ValidationAppException) as ctx, \
             patch(HASH_PATH), patch(VALIDATE_PATH):
            self._execute(_data(
                password='supersecret1',
                password_confirmation='different-pwd',
            ))

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)
        self.repo.save_admin_user_step.assert_not_called()


class TestPasswordOmittedOnReEdit(_UseCaseTestBase):
    """User came back to edit username/email; we must keep their hash."""

    PRIOR_HASH = '$argon2id$v=19$m=65536,t=3,p=4$prior-hash'

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(
            admin_user_completed=True,
            admin_user_data={
                'email': 'old@example.com',
                'username': 'old_username',
                'telephone': '3009999999',
                'first_name': 'Old',
                'last_name': 'Name',
                'password_hash': self.PRIOR_HASH,
            },
        )

    def test_empty_password_keeps_existing_hash(self):
        """The whole point of the feature: repo gets the *old* hash, the
        password validator is never called, and make_password is never
        called either (no rehash on no-op)."""
        with patch(HASH_PATH) as make_pwd, patch(VALIDATE_PATH) as validate_pwd:
            self._execute(_data(
                username='new_username',
                password='',
                password_confirmation='',
            ))

        validate_pwd.assert_not_called()
        make_pwd.assert_not_called()
        kwargs = self.repo.save_admin_user_step.call_args.kwargs
        self.assertEqual(kwargs['hashed_password'], self.PRIOR_HASH)

    def test_only_one_password_field_triggers_match_validation(self):
        """If the user filled password but left confirmation empty (or
        vice-versa) we must NOT silently fall back to "keep old hash" —
        that would be a confusing footgun."""
        with self.assertRaises(ValidationAppException) as ctx, \
             patch(HASH_PATH), patch(VALIDATE_PATH):
            self._execute(_data(
                password='newpassword1',
                password_confirmation='',
            ))

        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)


class TestPasswordReplacedOnReEdit(_UseCaseTestBase):
    """User explicitly typed a new password; the old hash is gone."""

    PRIOR_HASH = '$argon2id$v=19$m=65536,t=3,p=4$prior-hash'

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(
            admin_user_completed=True,
            admin_user_data={
                'email': 'old@example.com',
                'username': 'old_username',
                'telephone': '3009999999',
                'first_name': 'Old',
                'last_name': 'Name',
                'password_hash': self.PRIOR_HASH,
            },
        )

    def test_new_password_replaces_old_hash(self):
        with patch(HASH_PATH, return_value='new-hash') as make_pwd, \
             patch(VALIDATE_PATH):
            self._execute(_data(
                password='brandnewpwd1',
                password_confirmation='brandnewpwd1',
            ))

        make_pwd.assert_called_once_with('brandnewpwd1')
        kwargs = self.repo.save_admin_user_step.call_args.kwargs
        self.assertEqual(kwargs['hashed_password'], 'new-hash')
        self.assertNotEqual(kwargs['hashed_password'], self.PRIOR_HASH)


class TestUniquenessGuards(_UseCaseTestBase):
    """Username/email collisions still fail the way they always did,
    regardless of which password path was taken."""

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(admin_user_data={})

    def test_duplicate_username_raises_duplicate_email_code(self):
        self.repo.username_taken.return_value = True

        with self.assertRaises(OnboardingException) as ctx, \
             patch(HASH_PATH, return_value='h'), patch(VALIDATE_PATH):
            self._execute(_data())

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)
        self.repo.save_admin_user_step.assert_not_called()

    def test_duplicate_email_raises_duplicate_email_code(self):
        self.repo.email_taken.return_value = True

        with self.assertRaises(OnboardingException) as ctx, \
             patch(HASH_PATH, return_value='h'), patch(VALIDATE_PATH):
            self._execute(_data())

        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)
        self.repo.save_admin_user_step.assert_not_called()


class TestStateProjectionMirrorsHash(_UseCaseTestBase):
    """After the use case completes, the in-memory ORM mirror must carry
    the new hash so build_state_schema can surface
    ``admin_user_password_set=True`` without a re-read."""

    def setUp(self):
        super().setUp()
        self.reg = _orm_stub(admin_user_data={})

    def test_returned_state_has_password_set_flag(self):
        with patch(HASH_PATH, return_value='hashed-pwd'), patch(VALIDATE_PATH):
            state = self._execute(_data())

        self.assertTrue(state.admin_user_password_set)
        self.assertTrue(state.admin_user_completed)
        # Sensitive subset rules unchanged: no hash leaks out.
        self.assertNotIn('password_hash', state.admin_user_data)
