"""Shared helpers for login notification context (device label, geo)."""

from __future__ import annotations

from django.conf import settings


def parse_device_label(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    browser = 'Unknown'
    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'chrome/' in ua and 'chromium' not in ua:
        browser = 'Chrome'
    elif 'firefox/' in ua:
        browser = 'Firefox'
    elif 'safari/' in ua:
        browser = 'Safari'

    os_name = 'Unknown'
    if 'windows' in ua:
        os_name = 'Windows'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os_name = 'iOS'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'linux' in ua:
        os_name = 'Linux'
    return f'{browser} - {os_name}'


def resolve_login_location(request) -> str:
    """Best-effort location from reverse-proxy geo headers. Never looks up IP."""
    if not getattr(settings, 'TRUST_GEO_HEADERS', False):
        return 'Unknown location'
    meta = getattr(request, 'META', {}) or {}
    city = (meta.get('HTTP_CF_IPCITY') or meta.get('HTTP_X_GEO_CITY') or '').strip()
    country = (meta.get('HTTP_CF_IPCOUNTRY') or meta.get('HTTP_X_GEO_COUNTRY') or '').strip()
    if city and country:
        return f'{city}, {country}'
    if country:
        return country
    if city:
        return city
    return 'Unknown location'
