"""Unit tests de los endpoints admin (vistas aisladas, casos de uso parcheados)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.support.incidents.incident.domain.schemas import IncidentView
from platform.features.support.incidents.incident.presentation.admin_api import (
    IncidentDetailView,
    IncidentListView,
    IncidentStatusView,
)

_MOD = 'platform.features.support.incidents.incident.presentation.admin_api'


def _view(code='INC-2026-0001', status='open'):
    return IncidentView(id='11111111-1111-1111-1111-111111111111', code=code,
                        status=status, severity='high')


class AdminEndpointsTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk='admin-1')
        # El view construye _repo() y llama repo.count(): parcheamos para no tocar DB.
        self.repo_patcher = patch(f'{_MOD}._repo')
        repo = self.repo_patcher.start()
        repo.return_value.count.return_value = 1

    def tearDown(self):
        self.repo_patcher.stop()

    def _auth(self, request):
        force_authenticate(request, user=self.admin)
        return request

    # ── List ─────────────────────────────────────────────────────────────
    def test_list_passes_filters_and_returns_items(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/incidents/?status=open&company=arisoft&limit=10&offset=5'))
        with patch(f'{_MOD}.ListIncidentsUseCase') as UC:
            UC.return_value.execute.return_value = [_view()]
            resp = IncidentListView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['data']['items']), 1)
        self.assertEqual(resp.data['data']['page_size'], 10)
        self.assertEqual(resp.data['data']['total'], 1)
        filters, = UC.return_value.execute.call_args[0]
        kwargs = UC.return_value.execute.call_args[1]
        self.assertEqual(filters, {'status': 'open', 'schema_name': 'arisoft'})
        self.assertEqual(kwargs, {'limit': 10, 'offset': 5})

    def test_list_requires_authentication(self):
        req = self.factory.get('/api/v1/platform/incidents/')  # sin auth
        resp = IncidentListView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_list_rejects_malformed_date_with_400(self):
        req = self._auth(self.factory.get('/api/v1/platform/incidents/?from=abc'))
        with patch(f'{_MOD}.ListIncidentsUseCase') as UC:
            UC.return_value.execute.return_value = []
            resp = IncidentListView.as_view()(req)
        self.assertEqual(resp.status_code, 400)
        UC.return_value.execute.assert_not_called()

    def test_list_parses_valid_date_filter(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/incidents/?from=2026-01-01T00:00:00Z'))
        with patch(f'{_MOD}.ListIncidentsUseCase') as UC:
            UC.return_value.execute.return_value = []
            resp = IncidentListView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        filters, = UC.return_value.execute.call_args[0]
        self.assertIn('from_date', filters)

    def test_list_caps_limit(self):
        req = self._auth(self.factory.get('/api/v1/platform/incidents/?limit=99999'))
        with patch(f'{_MOD}.ListIncidentsUseCase') as UC:
            UC.return_value.execute.return_value = []
            IncidentListView.as_view()(req)
        self.assertEqual(UC.return_value.execute.call_args[1]['limit'], 100)

    def test_list_passes_module_and_functionality_filters(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/incidents/?module=settings&functionality=profile.edit'))
        with patch(f'{_MOD}.ListIncidentsUseCase') as UC:
            UC.return_value.execute.return_value = []
            IncidentListView.as_view()(req)
        filters, = UC.return_value.execute.call_args[0]
        self.assertEqual(filters['module'], 'settings')
        self.assertEqual(filters['functionality'], 'profile.edit')

    # ── Detail ───────────────────────────────────────────────────────────
    def test_detail_returns_incident(self):
        req = self._auth(self.factory.get('/x/'))
        with patch(f'{_MOD}.GetIncidentUseCase') as UC:
            UC.return_value.execute.return_value = _view()
            resp = IncidentDetailView.as_view()(req, incident_id='11111111-1111-1111-1111-111111111111')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['code'], 'INC-2026-0001')

    # ── Status ───────────────────────────────────────────────────────────
    def test_patch_status_valid(self):
        req = self._auth(self.factory.patch('/x/', {'status': 'resolved',
                                                    'resolution_notes': 'ok'}, format='json'))
        with patch(f'{_MOD}.build_update_status_use_case') as build_uc, \
             patch(f'{_MOD}.audit_log'):
            uc = MagicMock()
            uc.execute.return_value = _view(status='resolved')
            build_uc.return_value = uc
            resp = IncidentStatusView.as_view()(req, incident_id='11111111-1111-1111-1111-111111111111')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['status'], 'resolved')
        self.assertEqual(uc.execute.call_args[1]['status'], 'resolved')

    def test_patch_status_invalid_rejected(self):
        req = self._auth(self.factory.patch('/x/', {'status': 'bogus'}, format='json'))
        with patch(f'{_MOD}.build_update_status_use_case') as build_uc:
            resp = IncidentStatusView.as_view()(req, incident_id='11111111-1111-1111-1111-111111111111')
        self.assertGreaterEqual(resp.status_code, 400)
        build_uc.assert_not_called()

    def test_patch_status_requires_authentication(self):
        req = self.factory.patch('/x/', {'status': 'closed'}, format='json')
        resp = IncidentStatusView.as_view()(req, incident_id='11111111-1111-1111-1111-111111111111')
        self.assertEqual(resp.status_code, 401)
