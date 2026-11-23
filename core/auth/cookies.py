"""Helpers for setting/clearing HttpOnly auth cookies.

Four cookies are used:
  access_admin   — JWT access token for platform admins
  access_client  — JWT access token for tenant users
  refresh_admin  — opaque refresh token for platform admins
  refresh_client — opaque refresh token for tenant users

Plus ``device_client`` — high-entropy trusted-device serial (HttpOnly).
The frontend never sees token values — they live exclusively in
HttpOnly cookies sent automatically by the browser.
"""
from datetime import datetime
import re

from django.conf import settings
from django.utils.http import http_date


# ── Cookie names ─────────────────────────────────────────────────────────────

ACCESS_ADMIN_COOKIE  = 'access_admin'
ACCESS_CLIENT_COOKIE = 'access_client'
REFRESH_ADMIN_COOKIE  = 'refresh_admin'
REFRESH_CLIENT_COOKIE = 'refresh_client'
DEVICE_CLIENT_COOKIE = 'device_client'
DEVICE_ADMIN_COOKIE = 'device_admin'
_DEVICE_SERIAL_RE = re.compile(r'^[A-Za-z0-9._-]{16,128}$')
DEVICE_COOKIE_MAX_AGE = 90 * 86400

# Legacy names (kept for reference during migration)
# ACCESS_COOKIE_NAME       = 'token_client'
# ADMIN_ACCESS_COOKIE_NAME = 'token_admin'


# ── Cookie attribute helpers ─────────────────────────────────────────────────

def _base_kwargs() -> dict:
    """Common cookie attributes shared by all auth cookies."""
    secure = not settings.DEBUG
    samesite = getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax')
    domain = getattr(settings, 'AUTH_COOKIE_DOMAIN', None)
    return {
        'httponly': True,
        'secure': secure,
        'samesite': samesite,
        'domain': domain,
        'path': '/',
    }


def _access_max_age(*, admin: bool = False) -> int:
    """Max-age (seconds) for the access token cookie."""
    from core.auth.jwt_service import get_access_ttl_minutes
    return get_access_ttl_minutes('admin' if admin else 'client') * 60


def _refresh_max_age(*, admin: bool = False) -> int:
    """Max-age (seconds) for the refresh token cookie."""
    from core.auth.refresh_service import get_refresh_ttl_days
    return get_refresh_ttl_days('admin' if admin else 'client') * 86400


def _device_max_age() -> int:
    return DEVICE_COOKIE_MAX_AGE


def read_device_serial(request, *, admin: bool = False):
    name = DEVICE_ADMIN_COOKIE if admin else DEVICE_CLIENT_COOKIE
    raw = (request.COOKIES.get(name) or '').strip()
    if _DEVICE_SERIAL_RE.fullmatch(raw):
        return raw
    return None


def set_device_cookie(response, serial: str, *, admin: bool = False):
    """HttpOnly trusted-device serial. Survives logout; XSS cannot read it."""
    name = DEVICE_ADMIN_COOKIE if admin else DEVICE_CLIENT_COOKIE
    response.set_cookie(
        name,
        serial,
        max_age=_device_max_age(),
        **_base_kwargs(),
    )
    return response


def clear_device_cookie(response, *, admin: bool = False):
    name = DEVICE_ADMIN_COOKIE if admin else DEVICE_CLIENT_COOKIE
    _expire_cookie(response, name, _base_kwargs())
    return response


# ── Public API ───────────────────────────────────────────────────────────────

def set_auth_cookies(
    response,
    access_token: str,
    refresh_token: str,
    *,
    admin: bool = False,
    persistent: bool = True,
):
    """Set both access and refresh HttpOnly cookies on the response.

    ``persistent=True`` (Remember me): Max-Age matches token TTLs so the
    browser keeps the session after close.
    ``persistent=False``: session cookies (no Max-Age) — gone when the
    browser exits. Redis still caps the refresh token independently.
    """
    base = _base_kwargs()

    access_name = ACCESS_ADMIN_COOKIE if admin else ACCESS_CLIENT_COOKIE
    refresh_name = REFRESH_ADMIN_COOKIE if admin else REFRESH_CLIENT_COOKIE

    if persistent:
        response.set_cookie(
            access_name, access_token, max_age=_access_max_age(admin=admin), **base,
        )
        response.set_cookie(
            refresh_name, refresh_token, max_age=_refresh_max_age(admin=admin), **base,
        )
    else:
        response.set_cookie(access_name, access_token, **base)
        response.set_cookie(refresh_name, refresh_token, **base)
    return response


def _expire_cookie(response, name: str, base: dict):
    """Set a cookie with max_age=0 and expires in the past to force deletion."""
    response.set_cookie(name, '', max_age=0, expires=http_date(0), **base)


def clear_auth_cookies(response, *, admin: bool = False):
    """Delete both access and refresh cookies.

    Uses set_cookie with max_age=0 AND expires=epoch so that every
    browser honours the deletion — some ignore max_age=0 when expires
    is set to the current time.
    """
    base = _base_kwargs()

    access_name = ACCESS_ADMIN_COOKIE if admin else ACCESS_CLIENT_COOKIE
    refresh_name = REFRESH_ADMIN_COOKIE if admin else REFRESH_CLIENT_COOKIE

    _expire_cookie(response, access_name, base)
    _expire_cookie(response, refresh_name, base)

    # Also clear legacy cookies if present
    _expire_cookie(response, 'token_admin', base)
    _expire_cookie(response, 'token_client', base)
    return response
