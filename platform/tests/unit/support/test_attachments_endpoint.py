"""Unit tests del endpoint multipart de adjuntos (vista aislada, use case parcheado)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.support.incidents.incident.domain.schemas import (
    IncidentAttachment,
    IncidentView,
)
from platform.features.support.incidents.incident.presentation.api import (
    IncidentAttachmentsAPIView,
    ReportManualIncidentAPIView,
)

_API = 'platform.features.support.incidents.incident.presentation.api'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 16


class AttachmentsEndpointTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(pk='u-1', username='ana', email='ana@x.com')
        self.incident_id = uuid.uuid4()
        self.view = IncidentAttachmentsAPIView.as_view()

    def _post(self, files):
        req = self.factory.post(
            f'/api/v1/incidents/report/{self.incident_id}/attachments/',
            {'files': files}, format='multipart',
        )
        req.tenant = MagicMock(schema_name='acme')
        force_authenticate(req, user=self.user)
        return req

    def test_uploads_and_hides_object_names(self):
        stored = IncidentAttachment(
            id='a1', object_name='admin/support/incidents/x/a1.png', name='a.png',
            content_type='image/png', size=len(PNG), kind='image', uploaded_at='2026-10-07T12:00:00+00:00',
        )
        incident = IncidentView(id=str(self.incident_id), code='INC-1', status='open',
                                severity='low', attachments=[stored])
        with patch(f'{_API}.build_attach_media_use_case') as build:
            build.return_value.execute.return_value = incident
            resp = self.view(self._post([SimpleUploadedFile('a.png', PNG, 'image/png')]),
                             incident_id=self.incident_id)

        self.assertEqual(resp.status_code, 201)
        item = resp.data['data']['attachments'][0]
        self.assertEqual(item['name'], 'a.png')
        self.assertNotIn('object_name', item)
        kwargs = build.return_value.execute.call_args.kwargs
        self.assertEqual(kwargs['reporter_user_id'], 'u-1')
        self.assertEqual(kwargs['schema_name'], 'acme')
        self.assertEqual(kwargs['files'][0].data, PNG)

    def test_missing_files_rejected_without_use_case(self):
        with patch(f'{_API}.build_attach_media_use_case') as build:
            resp = self.view(self._post([]), incident_id=self.incident_id)
        self.assertEqual(resp.status_code, 400)
        build.assert_not_called()

    def test_too_many_files_rejected_without_use_case(self):
        files = [SimpleUploadedFile(f'{i}.png', PNG, 'image/png') for i in range(6)]
        with patch(f'{_API}.build_attach_media_use_case') as build:
            resp = self.view(self._post(files), incident_id=self.incident_id)
        self.assertEqual(resp.status_code, 400)
        build.assert_not_called()


class ManualReportKindEndpointTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(pk='u-1', username='ana', email='ana@x.com')
        self.view = ReportManualIncidentAPIView.as_view()

    def _post(self, payload):
        req = self.factory.post('/api/v1/incidents/report/manual/', payload, format='json')
        force_authenticate(req, user=self.user)
        return req

    def test_suggestion_kind_is_forwarded_and_id_returned(self):
        incident = IncidentView(id='inc-1', code='INC-2026-0009', status='open',
                                severity='low', kind='suggestion')
        with patch(f'{_API}.build_report_manual_use_case') as build, \
                patch(f'{_API}.incident_integration.resolve_client_session_id', return_value=''):
            build.return_value.execute.return_value = incident
            resp = self.view(self._post({
                'comment': 'Idea', 'conversation': {'messages': []},
                'source': 'toolbar', 'kind': 'suggestion',
            }))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['data'], {'id': 'inc-1', 'code': 'INC-2026-0009', 'kind': 'suggestion'})
        self.assertEqual(build.return_value.execute.call_args.kwargs['kind'], 'suggestion')

    def test_unknown_kind_rejected(self):
        with patch(f'{_API}.build_report_manual_use_case') as build:
            resp = self.view(self._post({
                'comment': 'x', 'conversation': {'messages': []}, 'kind': 'praise',
            }))
        self.assertEqual(resp.status_code, 400)
        build.assert_not_called()
