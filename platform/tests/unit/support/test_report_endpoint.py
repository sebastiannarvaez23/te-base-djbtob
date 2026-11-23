"""Unit tests del endpoint de reporte (vista aislada, use case parcheado)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.support.incidents.incident.domain.schemas import IncidentView
from platform.features.support.incidents.incident.presentation.api import ReportIncidentAPIView


class ReportEndpointTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(pk='u-1', username='ana', email='ana@x.com')
        self.user.company = MagicMock(id='c-1')
        self.view = ReportIncidentAPIView.as_view()

    def _post(self, payload):
        req = self.factory.post('/api/v1/incidents/report/', payload, format='json')
        force_authenticate(req, user=self.user)
        return req

    def test_valid_report_returns_201_with_code(self):
        incident = IncidentView(id='i', code='INC-2026-0007', status='open', severity='high')
        with patch(
            'platform.features.support.incidents.incident.presentation.api.build_report_use_case'
        ) as build:
            build.return_value.execute.return_value = incident
            resp = self.view(self._post({'token': 'a' * 30, 'comment': 'falló'}))

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['data']['code'], 'INC-2026-0007')
        # se pasó el token y el reporter
        _, kwargs = build.return_value.execute.call_args
        self.assertEqual(build.return_value.execute.call_args[0][0], 'a' * 30)
        self.assertEqual(kwargs['reporter']['username'], 'ana')

    def test_missing_token_is_rejected_without_calling_use_case(self):
        with patch(
            'platform.features.support.incidents.incident.presentation.api.build_report_use_case'
        ) as build:
            resp = self.view(self._post({'comment': 'sin token'}))
        self.assertGreaterEqual(resp.status_code, 400)
        build.assert_not_called()
