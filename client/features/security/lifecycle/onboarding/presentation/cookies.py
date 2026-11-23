"""HttpOnly cookie helpers for the onboarding token."""

from django.conf import settings
from django.utils.http import http_date

ONBOARDING_COOKIE = 'onboarding_token'


def _base_kwargs() -> dict:
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


def set_onboarding_cookie(response, token: str, max_age: int):
    response.set_cookie(ONBOARDING_COOKIE, token, max_age=max_age, **_base_kwargs())
    return response


def clear_onboarding_cookie(response):
    response.set_cookie(
        ONBOARDING_COOKIE, '', max_age=0, expires=http_date(0), **_base_kwargs(),
    )
    return response
