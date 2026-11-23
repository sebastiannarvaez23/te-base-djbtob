"""Sanitize browser console lines attached to an incident report."""
from __future__ import annotations

import base64
import json
from typing import Any

from platform.features.support.incidents.incident.application.redaction import redact_text_value

FRONTEND_LOG_LIMIT = 50
BROWSER_CONSOLE_LIMIT = FRONTEND_LOG_LIMIT
FRONTEND_LOG_MESSAGE_MAX = 2000
FRONTEND_LOG_LEVELS = frozenset({'log', 'info', 'warn', 'error', 'debug'})
FRONTEND_LOGS_HEADER = 'HTTP_X_WA_FRONTEND_LOGS'
FRONTEND_LOGS_HEADER_MAX = 8000

_SHORT_LEVELS = {
    'e': 'error',
    'w': 'warn',
    'i': 'info',
    'l': 'log',
    'd': 'debug',
}


def sanitize_frontend_logs(raw: Any) -> list[dict]:
    """Keep at most the last 50 well-formed console entries, redacted and clipped."""
    if not isinstance(raw, list):
        return []

    cleaned: list[dict] = []
    for item in raw[-FRONTEND_LOG_LIMIT:]:
        entry = _normalize_entry(item)
        if entry is None:
            continue
        cleaned.append(entry)
    return cleaned[-FRONTEND_LOG_LIMIT:]


def frontend_logs_from_request(request) -> list[dict]:
    """Decode ``X-base-Frontend-Logs`` (base64 JSON or plain JSON). Best-effort."""
    meta = getattr(request, 'META', None) or {}
    raw = meta.get(FRONTEND_LOGS_HEADER) or ''
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ''
    text = str(raw).strip()[:FRONTEND_LOGS_HEADER_MAX]
    if not text:
        return []
    parsed = _decode_header_payload(text)
    return sanitize_frontend_logs(parsed)


def merge_frontend_logs(*groups: Any) -> list[dict]:
    merged: list = []
    for group in groups:
        if isinstance(group, list):
            merged.extend(group)
    return sanitize_frontend_logs(merged)


sanitize_browser_console = sanitize_frontend_logs
merge_browser_console_entries = merge_frontend_logs
browser_console_from_request = frontend_logs_from_request


def _decode_header_payload(raw: str) -> Any:
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            padded = raw + ('=' * (-len(raw) % 4))
            decoded = decoder(padded.encode('ascii'), validate=False)
            return json.loads(decoded.decode('utf-8'))
        except Exception:
            continue
    try:
        return json.loads(raw)
    except Exception:
        return []


def _normalize_entry(item: Any) -> dict | None:
    if isinstance(item, str):
        message = _redact_message(item)
        if not message:
            return None
        return {'ts': '', 'level': 'log', 'message': message}

    if not isinstance(item, dict):
        return None

    if 'message' not in item and 'm' in item:
        item = {
            'ts': item.get('t') or item.get('ts') or '',
            'level': item.get('l') or item.get('level') or 'log',
            'message': item.get('m') or '',
        }

    level = str(item.get('level') or 'log').strip().lower()
    level = _SHORT_LEVELS.get(level, level)
    if level not in FRONTEND_LOG_LEVELS:
        level = 'log'

    message = _redact_message(str(item.get('message') or ''))
    if not message:
        return None

    return {
        'ts': str(item.get('ts') or '')[:40],
        'level': level,
        'message': message,
    }


def _redact_message(text: str) -> str:
    return redact_text_value(text, max_len=FRONTEND_LOG_MESSAGE_MAX)
