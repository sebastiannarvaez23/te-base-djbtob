"""JWT access token service.

Generates and validates short-lived, stateless access tokens.
No database lookup is required — validation is purely cryptographic.
"""
import jwt
from datetime import datetime, timedelta

from django.conf import settings


_ALGORITHM = 'HS256'


def get_access_ttl_minutes(user_type: str = 'client') -> int:
    """Read TOKEN_DURATION (minutes) from the matching parameter catalog.

    ``admin`` → admin catalog; everything else → client/runtime catalog.
    Both paths use cached facades (no direct PostgreSQL on the hot path).
    """
    try:
        if user_type == 'admin':
            from core.admin_parameters import get_admin_parameter
            value = get_admin_parameter('TOKEN_DURATION', default=None)
        else:
            from core.parameters import get_parameter
            value = get_parameter('TOKEN_DURATION', default=None)
        if value is None:
            return 1440
        return int(value)
    except Exception:
        return 1440  # 24h fallback


def create_access_token(
    user_id,
    user_type: str,
    schema_name: str = 'public',
    session_id: str = '',
    access_mode: str = 'full',
    username: str = '',
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: UUID or int of the authenticated user.
        user_type: 'admin' or 'client'.
        schema_name: Tenant schema (default 'public' for admin).
        session_id: Refresh token identifier stored in Redis.  Embedded in
            the JWT so that access-token authentication can verify the
            underlying session is still alive (immediate kill support).
        access_mode: ``full`` or ``billing_recovery`` (client tenants only).
        username: Optional display name for observability (no DB lookup on
            the request hot path).

    Returns:
        Encoded JWT string.
    """
    ttl = get_access_ttl_minutes(user_type)

    now = datetime.utcnow()
    payload = {
        'user_id': str(user_id),
        'user_type': user_type,
        'schema_name': schema_name,
        'sid': session_id,
        'access_mode': access_mode,
        'iat': now,
        'exp': now + timedelta(minutes=ttl),
    }
    if username:
        payload['username'] = str(username)[:150]
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid (bad signature, malformed, etc.).

    Returns:
        Decoded payload dict with user_id, user_type, schema_name, iat, exp.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
