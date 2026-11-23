"""Unit tests for testimonial HTTP views (use cases patched)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.configuration.landing.testimonial.domain.schemas import (
    PublicTestimonialPage,
    PublicTestimonialSchema,
    TestimonialPage,
    TestimonialPromptDecisionSchema,
    TestimonialPromptReceiptSchema,
    TestimonialPromptSettingsSchema,
    TestimonialSchema,
)
from platform.features.configuration.landing.testimonial.presentation.api import (
    TestimonialDetailView,
    TestimonialListCreateView,
)
from platform.features.configuration.landing.testimonial.presentation.prompt_api import (
    AckTestimonialPromptView,
    RecordTestimonialPromptSeenView,
    TestimonialPromptDecisionView,
)
from platform.features.configuration.landing.testimonial.presentation.public_api import (
    PublicTestimonialsAPIView,
)
from platform.features.configuration.landing.testimonial.presentation.settings_api import (
    TestimonialPromptSettingsView,
)
from platform.features.configuration.landing.testimonial.presentation.submit_api import (
    SubmitMyTestimonialAPIView,
)

pytestmark = pytest.mark.unit

AUTHOR_ID = uuid.uuid4()
ROW_ID = uuid.uuid4()
_ADMIN = 'platform.features.configuration.landing.testimonial.presentation.api'
_PROMPT = 'platform.features.configuration.landing.testimonial.presentation.prompt_api'
_SUBMIT = 'platform.features.configuration.landing.testimonial.presentation.submit_api'
_SETTINGS = 'platform.features.configuration.landing.testimonial.presentation.settings_api'
_PUBLIC = 'platform.features.configuration.landing.testimonial.presentation.public_api'


def _row(**overrides) -> TestimonialSchema:
    defaults = dict(
        id=ROW_ID,
        author_id=AUTHOR_ID,
        score=5,
        message='El picking guiado cambió la operación.',
        author_name='María Restrepo',
        locale='es',
        is_published=True,
        content_hash='a' * 64,
        seal='b' * 64,
        seal_algorithm='hmac-sha256-v1',
        signed_at=datetime.now(timezone.utc),
        signatory_id=str(AUTHOR_ID),
        canonical_payload='{}',
    )
    defaults.update(overrides)
    return TestimonialSchema(**defaults)


class TestimonialAdminApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk='admin-1', is_authenticated=True)

    def _auth(self, request):
        force_authenticate(request, user=self.admin)
        return request

    def test_list_requires_authentication(self):
        req = self.factory.get('/api/v1/platform/testimonials/')
        resp = TestimonialListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_detail_get_coerces_uuid(self):
        with patch(f'{_ADMIN}.GetTestimonialUseCase') as uc:
            uc.return_value.execute.return_value = _row()
            req = self._auth(self.factory.get(
                f'/api/v1/platform/testimonials/{ROW_ID}/',
            ))
            resp = TestimonialDetailView.as_view()(req, pk=str(ROW_ID))
        self.assertEqual(resp.status_code, 200)
        uc.return_value.execute.assert_called_once_with(ROW_ID)

    def test_list_paginated_uses_total(self):
        with patch(f'{_ADMIN}.ListTestimonialsUseCase') as uc:
            uc.return_value.execute.return_value = TestimonialPage(
                items=[_row()], total=3,
            )
            req = self._auth(self.factory.get(
                '/api/v1/platform/testimonials/?page=0&page_size=1',
            ))
            resp = TestimonialListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        payload = resp.data['data']
        self.assertEqual(payload['total'], 3)
        self.assertEqual(len(payload['items']), 1)


class TestimonialPromptApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(pk=AUTHOR_ID, is_authenticated=True)

    def _auth(self, request):
        force_authenticate(request, user=self.user)
        return request

    def test_decide_is_get(self):
        with patch(f'{_PROMPT}.DecideTestimonialPromptUseCase') as uc:
            uc.return_value.execute.return_value = TestimonialPromptDecisionSchema(
                should_prompt=True, delay_seconds=8,
            )
            req = self._auth(self.factory.get('/api/v1/testimonials/prompt/'))
            resp = TestimonialPromptDecisionView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        uc.return_value.execute.assert_called_once_with(AUTHOR_ID)
        self.assertTrue(resp.data['data']['should_prompt'])

    def test_seen_is_post_without_body(self):
        with patch(f'{_PROMPT}.RecordTestimonialPromptSeenUseCase') as uc:
            uc.return_value.execute.return_value = TestimonialPromptReceiptSchema(
                user_id=AUTHOR_ID,
                first_seen_at=datetime.now(timezone.utc),
            )
            req = self._auth(self.factory.post('/api/v1/testimonials/prompt/seen/'))
            resp = RecordTestimonialPromptSeenView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        uc.return_value.execute.assert_called_once_with(AUTHOR_ID)

    def test_ack_is_post_without_body(self):
        with patch(f'{_PROMPT}.AckTestimonialPromptUseCase') as uc:
            uc.return_value.execute.return_value = TestimonialPromptReceiptSchema(
                user_id=AUTHOR_ID,
                last_prompted_at=datetime.now(timezone.utc),
            )
            req = self._auth(self.factory.post('/api/v1/testimonials/prompt/ack/'))
            resp = AckTestimonialPromptView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        uc.return_value.execute.assert_called_once_with(AUTHOR_ID)


class TestimonialSubmitApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(
            pk=AUTHOR_ID, is_authenticated=True, company_id=uuid.uuid4(),
        )

    def test_submit_acks_after_success(self):
        signed = _row()
        with patch(f'{_SUBMIT}.SubmitMyTestimonialUseCase') as submit, patch(
            f'{_SUBMIT}.AckTestimonialPromptUseCase',
        ) as ack, patch(
            f'{_SUBMIT}.project_public',
            return_value=PublicTestimonialSchema(
                id=signed.id,
                score=signed.score,
                message=signed.message,
                author_name=signed.author_name,
                locale=signed.locale,
                signed_at=signed.signed_at,
                seal_fingerprint=signed.seal[:8],
            ),
        ):
            submit.return_value.execute.return_value = signed
            ack.return_value.execute.return_value = TestimonialPromptReceiptSchema(
                user_id=AUTHOR_ID,
            )
            req = self.factory.post(
                '/api/v1/testimonials/',
                {
                    'score': 5,
                    'message': 'El picking guiado cambió la operación.',
                    'accepted': True,
                },
                format='json',
            )
            force_authenticate(req, user=self.user)
            resp = SubmitMyTestimonialAPIView.as_view()(req)
        self.assertEqual(resp.status_code, 201)
        ack.return_value.execute.assert_called_once_with(AUTHOR_ID)


class TestimonialSettingsApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk='admin-1', is_authenticated=True)

    def test_get_settings_does_not_require_body(self):
        with patch(f'{_SETTINGS}.GetTestimonialPromptSettingsUseCase') as uc:
            uc.return_value.execute.return_value = TestimonialPromptSettingsSchema()
            req = self.factory.get('/api/v1/platform/testimonials/settings/')
            force_authenticate(req, user=self.admin)
            resp = TestimonialPromptSettingsView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        uc.return_value.execute.assert_called_once_with()


class TestimonialPublicApiTests(TestCase):

    def test_landing_list(self):
        item = PublicTestimonialSchema(
            id=ROW_ID,
            score=5,
            message='El picking guiado cambió la operación.',
            author_name='María Restrepo',
            locale='es',
            signed_at=datetime.now(timezone.utc),
            seal_fingerprint='abcd1234',
        )
        with patch(f'{_PUBLIC}.ListPublicTestimonialsUseCase') as uc:
            uc.return_value.execute.return_value = PublicTestimonialPage(
                items=[item], total=1,
            )
            req = APIRequestFactory().get('/api/v1/landing/testimonials/')
            resp = PublicTestimonialsAPIView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['data']), 1)
