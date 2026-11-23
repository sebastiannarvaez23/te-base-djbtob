"""
base MinIO bucket policy for profile pictures and brand assets.

``set_anonymous_read_patterns`` replaces the whole bucket policy, so every
bootstrap must apply the *merged* pattern list — otherwise whichever app
starts last drops the other world's public paths.
"""
from __future__ import annotations

from necore.storage.profile_bucket import (
    applied_public_policy,
    ensure_public_read_bucket,
    reset_ensure_bucket_state,
)

PROFILE_BUCKET = 'base'

ADMIN_PROFILE_PUBLIC_PATTERNS = (
    'admin/users/assets/profiles/*',
    'admin/assets/profile/*',
    'admin/assets/profile/avatar.png',
)

ADMIN_BRAND_ASSET_PUBLIC_PATTERNS = (
    'admin/assets/logos/*',
    'admin/assets/icon/*',
)

CLIENT_PROFILE_PUBLIC_PATTERNS = (
    'client/tenants/*/assets/profiles/*',
    'client/assets/profile/*',
    'client/assets/profile/avatar.png',
)

CLIENT_BRAND_ASSET_PUBLIC_PATTERNS = (
    'client/assets/logos/*',
    'client/assets/subs/*',
    'client/assets/icons/*',
)

CLIENT_REFERENCE_ILLUSTRATION_PUBLIC_PATTERNS = (
    'client/tenants/*/warehouse/inventory/reference/ilustration/*',
)

LIB_BRAND_ASSET_PUBLIC_PATTERNS = (
    'lib/assets/logos/*',
    'lib/assets/icons/*',
)

HANDBOOK_BRAND_ASSET_PUBLIC_PATTERNS = (
    'handbook/assets/logo/*',
)

BASE_PROFILE_PUBLIC_PATTERNS = list(
    dict.fromkeys(
        ADMIN_PROFILE_PUBLIC_PATTERNS
        + ADMIN_BRAND_ASSET_PUBLIC_PATTERNS
        + CLIENT_PROFILE_PUBLIC_PATTERNS
        + CLIENT_BRAND_ASSET_PUBLIC_PATTERNS
        + CLIENT_REFERENCE_ILLUSTRATION_PUBLIC_PATTERNS
        + LIB_BRAND_ASSET_PUBLIC_PATTERNS
        + HANDBOOK_BRAND_ASSET_PUBLIC_PATTERNS
    ),
)


def reset_ensure_profile_bucket_state() -> None:
    reset_ensure_bucket_state()


def ensure_profile_bucket(storage=None) -> None:
    """Create the shared base bucket and apply the merged anonymous-read policy."""
    ensure_public_read_bucket(
        PROFILE_BUCKET,
        BASE_PROFILE_PUBLIC_PATTERNS,
        storage=storage,
    )


__all__ = [
    'PROFILE_BUCKET',
    'ADMIN_PROFILE_PUBLIC_PATTERNS',
    'ADMIN_BRAND_ASSET_PUBLIC_PATTERNS',
    'CLIENT_PROFILE_PUBLIC_PATTERNS',
    'CLIENT_BRAND_ASSET_PUBLIC_PATTERNS',
    'CLIENT_REFERENCE_ILLUSTRATION_PUBLIC_PATTERNS',
    'LIB_BRAND_ASSET_PUBLIC_PATTERNS',
    'HANDBOOK_BRAND_ASSET_PUBLIC_PATTERNS',
    'BASE_PROFILE_PUBLIC_PATTERNS',
    'applied_public_policy',
    'ensure_profile_bucket',
    'reset_ensure_profile_bucket_state',
]
