"""Admin activity heartbeat: slides idle clock via JWT auth, returns 204."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.security.auth.auth.presentation.api import AdminActivityAPIView


def _admin_user():
    user = MagicMock()
    user.pk = uuid.uuid4()
    user.id = user.pk
    user.is_authenticated = True
    return user


class TestAdminActivityAPIView(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminActivityAPIView.as_view()

    def test_authenticated_post_returns_204(self):
        request = self.factory.post('/api/v1/platform/auth/activity/')
        force_authenticate(request, user=_admin_user())

        response = self.view(request)

        self.assertEqual(response.status_code, 204)

    def test_unauthenticated_post_is_rejected(self):
        request = self.factory.post('/api/v1/platform/auth/activity/')

        response = self.view(request)

        self.assertIn(response.status_code, (401, 403))
