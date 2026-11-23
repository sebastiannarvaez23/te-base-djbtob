"""Unit tests for merged base profile bucket policy."""
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.storage.profile_bucket import (
    ADMIN_BRAND_ASSET_PUBLIC_PATTERNS,
    ADMIN_PROFILE_PUBLIC_PATTERNS,
    CLIENT_BRAND_ASSET_PUBLIC_PATTERNS,
    CLIENT_PROFILE_PUBLIC_PATTERNS,
    HANDBOOK_BRAND_ASSET_PUBLIC_PATTERNS,
    LIB_BRAND_ASSET_PUBLIC_PATTERNS,
    PROFILE_BUCKET,
    BASE_PROFILE_PUBLIC_PATTERNS,
    applied_public_policy,
    ensure_profile_bucket,
    reset_ensure_profile_bucket_state,
)

pytestmark = pytest.mark.unit


class TestProfileBucketPolicy(TestCase):

    def setUp(self):
        reset_ensure_profile_bucket_state()

    def tearDown(self):
        reset_ensure_profile_bucket_state()

    def test_admin_brand_includes_support_chat_icons(self):
        self.assertIn('admin/assets/icon/*', ADMIN_BRAND_ASSET_PUBLIC_PATTERNS)

    def test_merged_patterns_include_admin_and_client(self):
        for pattern in ADMIN_PROFILE_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)
        for pattern in ADMIN_BRAND_ASSET_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)
        for pattern in CLIENT_PROFILE_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)
        for pattern in CLIENT_BRAND_ASSET_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)
        for pattern in LIB_BRAND_ASSET_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)
        for pattern in HANDBOOK_BRAND_ASSET_PUBLIC_PATTERNS:
            self.assertIn(pattern, BASE_PROFILE_PUBLIC_PATTERNS)

    def test_ensure_profile_bucket_applies_merged_policy(self):
        storage = MagicMock()
        storage.bucket_exists.return_value = True

        ensure_profile_bucket(storage)

        storage.set_anonymous_read_patterns.assert_called_once_with(
            PROFILE_BUCKET,
            BASE_PROFILE_PUBLIC_PATTERNS,
        )

    def test_client_bootstrap_does_not_drop_admin_patterns(self):
        """Regression: client-only ensure must still grant admin avatar paths."""
        storage = MagicMock()
        storage.bucket_exists.return_value = True

        ensure_profile_bucket(storage)

        patterns = storage.set_anonymous_read_patterns.call_args[0][1]
        self.assertIn('admin/users/assets/profiles/*', patterns)

    def test_records_applied_policy_for_startup_report(self):
        storage = MagicMock()
        storage.bucket_exists.return_value = True

        ensure_profile_bucket(storage)

        bucket, patterns = applied_public_policy()
        self.assertEqual(bucket, PROFILE_BUCKET)
        self.assertEqual(list(patterns), BASE_PROFILE_PUBLIC_PATTERNS)

    def test_injected_real_client_is_idempotent(self):
        """Identity apps pass a MinioStorageService instance; apply once."""
        from core.storage.infrastructure.minio_storage import MinioStorageService

        class _FakeMinio(MinioStorageService):
            def __init__(self):
                self.bucket_exists = MagicMock(return_value=True)
                self.create_bucket = MagicMock()
                self.set_anonymous_read_patterns = MagicMock()

        first = _FakeMinio()
        second = _FakeMinio()

        ensure_profile_bucket(first)
        ensure_profile_bucket(second)

        first.set_anonymous_read_patterns.assert_called_once()
        second.set_anonymous_read_patterns.assert_not_called()

    def test_skips_default_client_construction_after_real_apply(self):
        from unittest.mock import patch
        from core.storage.infrastructure.minio_storage import MinioStorageService

        class _FakeMinio(MinioStorageService):
            def __init__(self):
                self.bucket_exists = MagicMock(return_value=True)
                self.create_bucket = MagicMock()
                self.set_anonymous_read_patterns = MagicMock()

        ensure_profile_bucket(_FakeMinio())

        with patch('necore.storage.profile_bucket.MinioStorageService') as MockStorage:
            ensure_profile_bucket()

        MockStorage.assert_not_called()

    def test_mocks_always_apply(self):
        first = MagicMock()
        first.bucket_exists.return_value = True
        second = MagicMock()
        second.bucket_exists.return_value = True

        ensure_profile_bucket(first)
        ensure_profile_bucket(second)

        first.set_anonymous_read_patterns.assert_called_once()
        second.set_anonymous_read_patterns.assert_called_once()
