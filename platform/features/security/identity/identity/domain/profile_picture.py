"""Profile picture URL helpers for platform admin users (no ORM / storage deps)."""
from typing import Optional

from django.conf import settings

PROFILE_BUCKET = 'base'
PROFILE_PUBLIC_PATTERN = 'admin/users/assets/profiles/*'
DEFAULT_PROFILE_AVATAR_KEY = 'admin/assets/profile/avatar.png'
DEFAULT_AVATAR_PUBLIC_PATTERN = 'admin/assets/profile/*'


def profile_picture_url(object_key: Optional[str]) -> Optional[str]:
    """Permanent public URL for a stored MinIO object key."""
    key = (object_key or '').strip()
    if not key:
        return None
    return f'{settings.MINIO_PUBLIC_URL}/{PROFILE_BUCKET}/{key}'


def default_profile_picture_url() -> str:
    """Platform default avatar when the admin user has no custom picture."""
    return profile_picture_url(DEFAULT_PROFILE_AVATAR_KEY)  # type: ignore[return-value]


def resolve_profile_picture_url(object_key: Optional[str]) -> str:
    """Avatar URL for session payloads — always returns a usable URL."""
    return profile_picture_url(object_key) or default_profile_picture_url()


def user_picture_object_key(user) -> Optional[str]:
    """MinIO object key stored on the admin user model, if any."""
    raw = getattr(user, 'picture', None)
    if raw is None:
        return None
    try:
        if not raw:
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(raw, str):
        key = raw.strip()
    else:
        key = (getattr(raw, 'name', None) or '').strip()
    return key or None
