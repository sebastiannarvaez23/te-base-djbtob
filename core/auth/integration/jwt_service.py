"""JWT mint/verify for Integration Application access tokens.

Separate crypto plane from human (admin/client) cookie JWTs:
uses ``INTEGRATION_JWT_SECRET`` when set, otherwise falls back to
``SECRET_KEY`` (dev / tests). Claims are intentionally distinct so a
human token can never satisfy the integration authenticator and vice versa.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Sequence

import jwt
from django.conf import settings

from core.ids import uuid7

INTEGRATION_USER_TYPE = 'integration'
INTEGRATION_AUDIENCE = 'base.integration'
_ALGORITHM = 'HS256'


def _signing_key() -> str:
    dedicated = getattr(settings, 'INTEGRATION_JWT_SECRET', '') or ''
    return dedicated or settings.SECRET_KEY


def get_integration_access_ttl_seconds() -> int:
    """Access-token lifetime for M2M apps (default 1 hour)."""
    return int(getattr(settings, 'INTEGRATION_TOKEN_TTL_SECONDS', 3600))


def create_integration_access_token(
    *,
    app_id: str,
    client_id: str,
    schema_name: str,
    scopes: Sequence[str],
    jti: str | None = None,
) -> tuple[str, dict]:
    """Create a signed integration access token.

    Returns:
        (encoded_jwt, payload_dict) — payload includes ``exp`` as datetime
        for callers that need ``expires_in`` without decoding again.
    """
    ttl = get_integration_access_ttl_seconds()
    now = datetime.utcnow()
    payload = {
        'user_type': INTEGRATION_USER_TYPE,
        'aud': INTEGRATION_AUDIENCE,
        'app_id': str(app_id),
        'client_id': client_id,
        'schema_name': schema_name,
        'scopes': list(scopes),
        'jti': jti or uuid7().hex,
        'iat': now,
        'exp': now + timedelta(seconds=ttl),
    }
    token = jwt.encode(payload, _signing_key(), algorithm=_ALGORITHM)
    return token, payload


def decode_integration_access_token(token: str) -> dict:
    """Decode and validate an integration access token.

    Raises:
        jwt.ExpiredSignatureError / jwt.InvalidTokenError
    """
    return jwt.decode(
        token,
        _signing_key(),
        algorithms=[_ALGORITHM],
        audience=INTEGRATION_AUDIENCE,
    )


def normalize_scopes(scopes: Iterable[str] | None) -> list[str]:
    """Deduplicate and sort scopes for stable token/API output."""
    if not scopes:
        return []
    return sorted({s.strip() for s in scopes if s and s.strip()})
