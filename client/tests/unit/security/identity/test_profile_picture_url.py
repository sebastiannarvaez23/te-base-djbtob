"""Unit tests for profile picture URL helpers."""
from unittest import TestCase
from unittest.mock import patch

import pytest

from client.features.security.identity.identity.domain.profile_picture import (
    DEFAULT_PROFILE_AVATAR_KEY,
    default_profile_picture_url,
    profile_picture_url,
    resolve_profile_picture_url,
)

pytestmark = pytest.mark.unit


class TestProfilePictureUrl(TestCase):

    @patch('client.features.security.identity.identity.domain.profile_picture.settings')
    def test_profile_picture_url_returns_none_for_empty_key(self, settings):
        settings.MINIO_PUBLIC_URL = 'http://minio.local'

        self.assertIsNone(profile_picture_url(None))
        self.assertIsNone(profile_picture_url(''))

    @patch('client.features.security.identity.identity.domain.profile_picture.settings')
    def test_profile_picture_url_builds_public_url(self, settings):
        settings.MINIO_PUBLIC_URL = 'http://minio.local'
        key = 'client/tenants/acme/assets/profiles/pic-user.jpg'

        url = profile_picture_url(key)

        self.assertEqual(url, f'http://minio.local/base/{key}')

    @patch('client.features.security.identity.identity.domain.profile_picture.settings')
    def test_default_profile_picture_url_points_to_platform_avatar(self, settings):
        settings.MINIO_PUBLIC_URL = 'http://minio.local'

        url = default_profile_picture_url()

        self.assertEqual(url, f'http://minio.local/base/{DEFAULT_PROFILE_AVATAR_KEY}')

    @patch('client.features.security.identity.identity.domain.profile_picture.settings')
    def test_resolve_profile_picture_url_falls_back_to_default(self, settings):
        settings.MINIO_PUBLIC_URL = 'http://minio.local'

        url = resolve_profile_picture_url(None)

        self.assertIn(DEFAULT_PROFILE_AVATAR_KEY, url)

    @patch('client.features.security.identity.identity.domain.profile_picture.settings')
    def test_resolve_profile_picture_url_uses_custom_key(self, settings):
        settings.MINIO_PUBLIC_URL = 'http://minio.local'
        key = 'client/tenants/acme/assets/profiles/pic-user.jpg'

        url = resolve_profile_picture_url(key)

        self.assertEqual(url, f'http://minio.local/base/{key}')
