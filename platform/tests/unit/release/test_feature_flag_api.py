"""FASE 3 — Tests unitarios de la API admin de feature flags.

Vistas aisladas con use cases parcheados. Ejecutar:

    pytest core/tests/unit/flags/ platform/tests/unit/release/
"""

from __future__ import annotations

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from core.errors import ConflictException
from core.errors.codes import AppErrorCode
from platform.features.release.feature_flag.feature_flag.domain.schemas import FeatureFlagSchema
from platform.features.release.feature_flag.feature_flag.presentation.api import (
    FeatureFlagDetailView,
    FeatureFlagListCreateView,
)

_MOD = 'platform.features.release.feature_flag.feature_flag.presentation.api'


def _flag(**overrides) -> FeatureFlagSchema:
    defaults = dict(
        id=uuid.uuid4(),
        key='picking.route_v2',
        name='Picking route v2',
        description='',
        flag_type='RELEASE',
        status='ACTIVE',
        enabled=True,
        owner='',
        scopes=[],
    )
    defaults.update(overrides)
    return FeatureFlagSchema(**defaults)


class FeatureFlagApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk='admin-1', is_authenticated=True)

    def _auth(self, request):
        force_authenticate(request, user=self.admin)
        return request

    # ── Auth ──────────────────────────────────────────────────────────────

    def test_list_requires_authentication(self):
        req = self.factory.get('/api/v1/platform/feature-flags/')
        resp = FeatureFlagListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_create_requires_authentication(self):
        req = self.factory.post(
            '/api/v1/platform/feature-flags/',
            {'key': 'a.b', 'name': 'Name here'},
            format='json',
        )
        resp = FeatureFlagListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_detail_requires_authentication(self):
        req = self.factory.get(f'/api/v1/platform/feature-flags/{uuid.uuid4()}/')
        resp = FeatureFlagDetailView.as_view()(req, pk=uuid.uuid4())
        self.assertEqual(resp.status_code, 401)

    # ── Validación de payload ─────────────────────────────────────────────

    def test_create_rejects_invalid_key(self):
        req = self._auth(self.factory.post(
            '/api/v1/platform/feature-flags/',
            {'key': 'Invalid Key', 'name': 'Name here'},
            format='json',
        ))
        resp = FeatureFlagListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_invalid_scope_type(self):
        req = self._auth(self.factory.post(
            '/api/v1/platform/feature-flags/',
            {
                'key': 'picking.route_v2',
                'name': 'Picking route v2',
                'scopes': [
                    {'scope_type': 'ZONE', 'scope_value': 'x'},
                ],
            },
            format='json',
        ))
        resp = FeatureFlagListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_duplicate_key(self):
        req = self._auth(self.factory.post(
            '/api/v1/platform/feature-flags/',
            {'key': 'picking.route_v2', 'name': 'Picking route v2'},
            format='json',
        ))
        with patch(f'{_MOD}.CreateFeatureFlagUseCase') as UC:
            UC.return_value.execute.side_effect = ConflictException(
                AppErrorCode.FLAG_DUPLICATE_KEY,
            )
            resp = FeatureFlagListCreateView.as_view()(req)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['error']['code'], AppErrorCode.FLAG_DUPLICATE_KEY.value)

    def test_create_success(self):
        created = _flag()
        req = self._auth(self.factory.post(
            '/api/v1/platform/feature-flags/',
            {
                'key': 'picking.route_v2',
                'name': 'Picking route v2',
                'status': 'ACTIVE',
                'enabled': True,
                'scopes': [
                    {'scope_type': 'COUNTRY', 'scope_value': 'Colombia'},
                ],
            },
            format='json',
        ))
        with patch(f'{_MOD}.CreateFeatureFlagUseCase') as UC, \
             patch(f'{_MOD}.audit_log') as audit:
            UC.return_value.execute.return_value = created
            resp = FeatureFlagListCreateView.as_view()(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['data']['key'], 'picking.route_v2')
        audit.assert_called_once()

    def test_list_success(self):
        req = self._auth(self.factory.get('/api/v1/platform/feature-flags/'))
        with patch(f'{_MOD}.GetAllFeatureFlagsUseCase') as UC:
            UC.return_value.execute.return_value = [_flag()]
            resp = FeatureFlagListCreateView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['data']), 1)

    def test_update_rejects_invalid_scope_type(self):
        pk = uuid.uuid4()
        req = self._auth(self.factory.patch(
            f'/api/v1/platform/feature-flags/{pk}/',
            {'scopes': [{'scope_type': 'ZONE', 'scope_value': 'x'}]},
            format='json',
        ))
        resp = FeatureFlagDetailView.as_view()(req, pk=pk)
        self.assertEqual(resp.status_code, 400)
