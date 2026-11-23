"""Unit tests for the four onboarding step endpoints.

The views (``OnboardingCompanyAPIView``, ``OnboardingAdminUserAPIView``,
``OnboardingSubscriptionAPIView``, ``OnboardingPaymentAPIView``) all
extend ``_StepAPIView`` and share the same orchestration:

  1. Resolve ``registration_id`` from the onboarding cookie. Missing or
     unknown token → ``OnboardingException(ONBOARDING_INVALID_TOKEN)`` →
     401 from the global handler.
  2. Validate the body via the view's ``body_class``. Invalid → 400; the
     use case never runs.
  3. Build the schema, dispatch to the use case, audit the
     ``STEP_COMPLETED`` event, return the new state.

These tests exercise the orchestration layer — the use cases themselves
have separate unit tests. We patch each step's use case class and the
parameter / factory helpers so no DB or Redis is touched.

LOCATION strings are file-unique to keep AnonRateThrottle's per-IP
bucket from bleeding across the test suite (LocMem dedups by LOCATION).
"""
from unittest import mock
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import django
from django.conf import settings as dj_settings
import pytest

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from core.errors import AppErrorCode, OnboardingException

from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus, OnboardingStep,
)
from client.features.security.lifecycle.onboarding.domain.schemas import OnboardingStateSchema
from client.features.security.lifecycle.onboarding.presentation.api import (
    OnboardingAdminUserAPIView,
    OnboardingCompanyAPIView,
    OnboardingPaymentAPIView,
    OnboardingSubscriptionAPIView,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import ONBOARDING_COOKIE


pytestmark = pytest.mark.unit

TestCase = SimpleTestCase

VIEW_PATH = 'client.features.security.lifecycle.onboarding.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-onbsteps'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-onbsteps'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-onbsteps'},
}

REG_ID = UUID('33333333-3333-3333-3333-333333333333')
SUBSCRIPTION_ID = UUID('44444444-4444-4444-4444-444444444444')


def _state(current_step=OnboardingStep.ADMIN_USER, **overrides):
    """Build a minimal valid OnboardingStateSchema for the use-case return."""
    base = dict(
        id=REG_ID,
        status=OnboardingStatus.IN_PROGRESS,
        current_step=current_step,
        email='founder@example.com',
        nit='',
        schema_name='',
        company_data_completed=False,
        admin_user_completed=False,
        subscription_selected=False,
        payment_completed=False,
        requires_payment=True,
        company_data={},
        subscription_data={},
        expires_at='2026-05-05T00:00:00+00:00',
    )
    base.update(overrides)
    return OnboardingStateSchema(**base)


def _post(view_cls, data, cookie='cookie-token'):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/onboarding/step/', data, format='json')
    if cookie:
        request.COOKIES[ONBOARDING_COOKIE] = cookie
    return view_cls.as_view()(request)


# ── Sample bodies ───────────────────────────────────────────────────────────
# One known-good payload per step, kept minimal — body validators have their
# own unit tests; here we only need bodies that pass so the orchestration
# proceeds to the use case.

GOOD_COMPANY = dict(
    name='Acme Logistics',
    nit='900123456-7',
    address='Cra 1 # 2-3',
    country='Colombia',
    country_code='CO',
    state='Cundinamarca',
    city='Bogota',
    city_id='0f15d58f-1ed6-4019-a3b7-22861f9dbc82',
)

GOOD_ADMIN = dict(
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

GOOD_SUBSCRIPTION = dict(subscription_id=str(SUBSCRIPTION_ID))

GOOD_PAYMENT = dict(
    processor_token='tok_abcdefgh1234',
    holder='Jane Doe',
    last4='4242',
    expiry_month=12,
    expiry_year=2030,
)


# ── Shared base ─────────────────────────────────────────────────────────────

@override_settings(CACHES=LOCMEM_CACHES)
class _StepViewTestBase(TestCase):
    """Patches the cookie-resolution machinery and audit_log.

    Each subclass picks the view + use-case-symbol it exercises so the
    use case's ``execute`` can be observed.
    """

    use_case_symbol: str = ''  # name of the use-case class on the view module
    view_cls = None
    sample_body: dict = {}
    expected_step_name: str = ''

    def setUp(self):
        # Stub the factory functions so we don't construct the real Redis
        # token-store or the real repository.
        self.token_store = MagicMock()
        self.token_store.resolve.return_value = REG_ID

        repo_patch = mock.patch(f'{VIEW_PATH}._repo', return_value=MagicMock())
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

        store_patch = mock.patch(
            f'{VIEW_PATH}._token_store', return_value=self.token_store,
        )
        store_patch.start()
        self.addCleanup(store_patch.stop)

        # Each step view's use case is patched so we can observe execute().
        if self.use_case_symbol:
            uc_patch = mock.patch(f'{VIEW_PATH}.{self.use_case_symbol}')
            self.use_case_cls = uc_patch.start()
            self.addCleanup(uc_patch.stop)
            self.use_case_instance = self.use_case_cls.return_value
            self.use_case_instance.execute.return_value = _state()

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)


# ── Cookie resolution (run once via the Company view; behaviour is shared) ──

class TestCookieResolution(_StepViewTestBase):
    """Cookie handling lives in ``_resolve_registration_id`` and is shared
    by every step view. We exercise it via the Company view since the
    code path is identical for the others."""

    use_case_symbol = 'SubmitCompanyStepUseCase'
    view_cls = OnboardingCompanyAPIView
    sample_body = GOOD_COMPANY
    expected_step_name = 'company'

    def test_missing_cookie_returns_401(self):
        """No cookie → no registration → ONB_007. The error envelope must
        match the registered code so the FE can prompt for resume."""
        response = _post(self.view_cls, self.sample_body, cookie=None)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'ONB_007')
        self.use_case_instance.execute.assert_not_called()

    def test_unknown_cookie_token_returns_401(self):
        """Cookie present but token store has no mapping (expired or
        unknown) → same 401, same code. Audit must not fire."""
        self.token_store.resolve.return_value = None

        response = _post(self.view_cls, self.sample_body)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'ONB_007')
        self.audit_mock.assert_not_called()

    def test_invalid_cookie_does_not_run_body_validation(self):
        """Cookie failure short-circuits before body validation — even an
        empty body should still yield ONB_007, not VAL_001. Confirms the
        order of checks in ``post()``."""
        self.token_store.resolve.return_value = None

        response = _post(self.view_cls, {})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'ONB_007')


# ── Per-step happy path + body validation ──────────────────────────────────

class _PerStepBehaviour:
    """Mixin: body validation, happy path, audit, and use-case dispatch.

    Uses the subclass-defined view + use-case symbol so the same checks
    run for all four step endpoints without copy-paste.
    """

    def test_invalid_body_is_400(self):
        response = _post(self.view_cls, {})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_invalid_body_does_not_audit(self):
        _post(self.view_cls, {})
        self.audit_mock.assert_not_called()

    def test_happy_path_returns_200_with_state(self):
        response = _post(self.view_cls, self.sample_body)

        self.assertEqual(response.status_code, 200)
        # wrap_response puts the state under "data".
        self.assertEqual(response.data['data']['id'], str(REG_ID))

    def test_happy_path_dispatches_use_case_with_registration_id(self):
        """The use case receives the resolved registration_id (from the
        cookie) and the schema built from the body — never the raw
        request body."""
        _post(self.view_cls, self.sample_body)

        self.use_case_instance.execute.assert_called_once()
        args = self.use_case_instance.execute.call_args.args
        self.assertEqual(args[0], REG_ID)
        # args[1] is the pydantic schema; just checking it's not the
        # raw dict the client posted (the view must build the schema).
        self.assertNotIsInstance(args[1], dict)

    def test_happy_path_audits_step_completion(self):
        _post(self.view_cls, self.sample_body)

        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        self.assertEqual(args[1], 'CompanyRegistration')
        self.assertEqual(args[2], REG_ID)
        self.assertEqual(args[3], 'STEP_COMPLETED')
        self.assertIn(f'step={self.expected_step_name}', args[4])


class TestCompanyStep(_PerStepBehaviour, _StepViewTestBase):
    use_case_symbol = 'SubmitCompanyStepUseCase'
    view_cls = OnboardingCompanyAPIView
    sample_body = GOOD_COMPANY
    expected_step_name = 'company'

    def test_duplicate_nit_returns_409(self):
        """The use case may raise ONBOARDING_DUPLICATE_NIT after schema
        normalisation; the view must let it propagate so the handler
        produces 409 with the right code."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_DUPLICATE_NIT,
        )

        response = _post(self.view_cls, self.sample_body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'ONB_006')
        self.audit_mock.assert_not_called()


class TestAdminUserStep(_PerStepBehaviour, _StepViewTestBase):
    use_case_symbol = 'SubmitAdminUserStepUseCase'
    view_cls = OnboardingAdminUserAPIView
    sample_body = GOOD_ADMIN
    expected_step_name = 'admin_user'


class TestSubscriptionStep(_PerStepBehaviour, _StepViewTestBase):
    use_case_symbol = 'SubmitSubscriptionStepUseCase'
    view_cls = OnboardingSubscriptionAPIView
    sample_body = GOOD_SUBSCRIPTION
    expected_step_name = 'subscription'


class TestPaymentStep(_PerStepBehaviour, _StepViewTestBase):
    use_case_symbol = 'SubmitPaymentStepUseCase'
    view_cls = OnboardingPaymentAPIView
    sample_body = GOOD_PAYMENT
    expected_step_name = 'payment'
