"""Unit tests for finalize + published-policy onboarding API views."""

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

from core.errors import AppErrorCode, NotFoundException, OnboardingException

from client.features.security.lifecycle.onboarding.domain.schemas import FinalizeResultSchema
from client.features.security.lifecycle.onboarding.presentation.api import (
    OnboardingFinalizeAPIView,
    OnboardingPublishedPolicyAPIView,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import ONBOARDING_COOKIE
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
)
from platform.features.compliance.policy.policy.domain.schemas import PolicyCountryContentSchema


pytestmark = pytest.mark.unit

TestCase = SimpleTestCase

VIEW_PATH = 'client.features.security.lifecycle.onboarding.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-onbpriv'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-onbpriv'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-onbpriv'},
}

REG_ID = UUID('55555555-5555-5555-5555-555555555555')
POLICY_ID = UUID('66666666-6666-6666-6666-666666666666')

GOOD_FINALIZE = dict(
    privacy_accepted=True,
    privacy_content_hash='a' * 64,
    privacy_country='CO',
    terms_accepted=True,
    terms_content_hash='b' * 64,
)


def _content(**overrides):
    base = dict(
        policy_id=POLICY_ID,
        policy_code='PRIVACY-POLICY',
        audience=PolicyAudience.CLIENT,
        country='CO',
        version=2,
        status=PolicyCountryStatus.PUBLISHED,
        title='Política de privacidad',
        markdown='# Hola',
        object_key='x.md',
        content_hash='a' * 64,
        byte_size=10,
    )
    base.update(overrides)
    return PolicyCountryContentSchema(**base)


@override_settings(CACHES=LOCMEM_CACHES)
class FinalizeViewTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.token_store = MagicMock()
        self.token_store.resolve.return_value = REG_ID

        token_patch = mock.patch(f'{VIEW_PATH}._token_store', return_value=self.token_store)
        token_patch.start()
        self.addCleanup(token_patch.stop)

        repo_patch = mock.patch(f'{VIEW_PATH}._repo', return_value=MagicMock())
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        audit_patch.start()
        self.addCleanup(audit_patch.stop)

        cookie_patch = mock.patch(f'{VIEW_PATH}.clear_onboarding_cookie', side_effect=lambda r: r)
        cookie_patch.start()
        self.addCleanup(cookie_patch.stop)

        uc_patch = mock.patch(f'{VIEW_PATH}.compose_finalize_use_case')
        self.compose = uc_patch.start()
        self.addCleanup(uc_patch.stop)
        self.use_case = self.compose.return_value
        self.use_case.execute.return_value = FinalizeResultSchema(
            registration_id=REG_ID,
            company_id=uuid4(),
            email_confirmation_required=False,
        )

    def _post(self, data, cookie='tok'):
        request = self.factory.post('/api/v1/onboarding/finalize/', data, format='json')
        if cookie:
            request.COOKIES[ONBOARDING_COOKIE] = cookie
        return OnboardingFinalizeAPIView.as_view()(request)

    def test_happy_path_forwards_privacy_fields(self):
        response = self._post(GOOD_FINALIZE)
        self.assertEqual(response.status_code, 201)
        kwargs = self.use_case.execute.call_args.kwargs
        self.assertTrue(kwargs['privacy_accepted'])
        self.assertEqual(kwargs['privacy_content_hash'], 'a' * 64)
        self.assertEqual(kwargs['privacy_country'], 'CO')
        self.assertTrue(kwargs['terms_accepted'])
        self.assertEqual(kwargs['terms_content_hash'], 'b' * 64)
        self.assertIsNotNone(kwargs['sign_context'])

    def test_missing_privacy_body_returns_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)
        self.use_case.execute.assert_not_called()

    def test_privacy_false_still_reaches_use_case(self):
        """Body validator accepts false; use case enforces ONB_013."""
        self.use_case.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_PRIVACY_REQUIRED,
        )
        response = self._post({
            **GOOD_FINALIZE,
            'privacy_accepted': False,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'ONB_013')

    def test_missing_cookie_returns_401(self):
        response = self._post(GOOD_FINALIZE, cookie=None)
        self.assertEqual(response.status_code, 401)
        self.use_case.execute.assert_not_called()


@override_settings(CACHES=LOCMEM_CACHES)
class PublishedPolicyViewTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.token_store = MagicMock()
        self.token_store.resolve.return_value = REG_ID
        self.repo = MagicMock()
        self.get_uc = MagicMock()
        self.get_uc.execute.return_value = _content()

        token_patch = mock.patch(f'{VIEW_PATH}._token_store', return_value=self.token_store)
        token_patch.start()
        self.addCleanup(token_patch.stop)

        repo_patch = mock.patch(f'{VIEW_PATH}._repo', return_value=self.repo)
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

    def _get(self, *, code='PRIVACY-POLICY', query='', cookie='tok'):
        request = self.factory.get(f'/api/v1/onboarding/policies/{code}/{query}')
        if cookie:
            request.COOKIES[ONBOARDING_COOKIE] = cookie

        with mock.patch(
            'platform.features.compliance.policy.policy.application.public_use_cases'
            '.GetPublishedPolicyByCodeUseCase',
            return_value=self.get_uc,
        ), mock.patch(
            'platform.features.compliance.policy.policy.infrastructure.repositories'
            '.DjangoPolicyRepository',
        ), mock.patch('core.storage.MinioStorageService'):
            return OnboardingPublishedPolicyAPIView.as_view()(request, code=code)

    def test_query_country_loads_published_policy(self):
        response = self._get(query='?country=CO')
        self.assertEqual(response.status_code, 200)
        self.get_uc.execute.assert_called_once_with('PRIVACY-POLICY', 'CO')
        self.assertEqual(response.data['data']['policy_code'], 'PRIVACY-POLICY')
        self.assertEqual(response.data['data']['content_hash'], 'a' * 64)
        self.assertNotIn('object_key', response.data['data'])

    def test_falls_back_to_registration_country_code(self):
        reg = MagicMock()
        reg.company_data = {'country': 'Colombia', 'country_code': 'co'}
        self.repo.get.return_value = reg

        response = self._get(query='')
        self.assertEqual(response.status_code, 200)
        self.get_uc.execute.assert_called_once_with('PRIVACY-POLICY', 'CO')

    def test_missing_country_returns_onb_014(self):
        reg = MagicMock()
        reg.company_data = {'country': 'Colombia'}
        self.repo.get.return_value = reg

        response = self._get(query='')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'ONB_014')
        self.get_uc.execute.assert_not_called()

    def test_policy_not_found_propagates(self):
        self.get_uc.execute.side_effect = NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        response = self._get(query='?country=CO')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'POL_001')
