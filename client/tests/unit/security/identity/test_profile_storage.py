"""Unit tests for profile storage bootstrap."""
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from client.features.security.identity.identity.domain.profile_picture import (
    DEFAULT_PROFILE_AVATAR_KEY,
)
from client.features.security.identity.identity.infrastructure.profile_storage import (
    PUBLIC_READ_PATTERNS,
    _DEFAULT_AVATAR_FILE,
    ensure_profile_storage,
)
from core.storage.profile_bucket import BASE_PROFILE_PUBLIC_PATTERNS, PROFILE_BUCKET

pytestmark = pytest.mark.unit


class TestEnsureProfileStorage(TestCase):

    def test_creates_bucket_policy_and_uploads_default_avatar(self):
        storage = MagicMock()
        storage.bucket_exists.return_value = False
        storage.file_exists.return_value = False

        with patch.object(Path, 'is_file', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b'png-bytes'
                with patch.object(Path, 'read_bytes', return_value=b'png-bytes'):
                    ensure_profile_storage(storage)

        storage.create_bucket.assert_called_once()
        storage.set_anonymous_read_patterns.assert_called_once_with(
            PROFILE_BUCKET,
            BASE_PROFILE_PUBLIC_PATTERNS,
        )
        upload_call = storage.upload_file.call_args[0][0]
        self.assertEqual(upload_call.bucket, PROFILE_BUCKET)
        self.assertEqual(upload_call.object_name, DEFAULT_PROFILE_AVATAR_KEY)
        self.assertEqual(upload_call.content_type, 'image/png')

    def test_skips_upload_when_default_avatar_already_exists(self):
        storage = MagicMock()
        storage.bucket_exists.return_value = True
        storage.file_exists.return_value = True

        ensure_profile_storage(storage)

        storage.upload_file.assert_not_called()
        storage.set_anonymous_read_patterns.assert_called_once()

    def test_default_avatar_asset_file_is_bundled(self):
        self.assertTrue(_DEFAULT_AVATAR_FILE.is_file(), msg=str(_DEFAULT_AVATAR_FILE))
