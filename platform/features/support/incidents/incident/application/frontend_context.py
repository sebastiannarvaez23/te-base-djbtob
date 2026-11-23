"""Sanitize client frontend context attached to an incident report."""
from __future__ import annotations

import copy
import json
from typing import Any

from platform.features.support.incidents.incident.application.frontend_logs import (
    BROWSER_CONSOLE_LIMIT,
    merge_browser_console_entries,
)
from platform.features.support.incidents.incident.application.redaction import (
    is_sensitive_key,
    redact_text_value,
)
from platform.features.support.incidents.incident.domain.schemas import FrontendContextSnapshot

FRONTEND_CONTEXT_MAX_BYTES = 120_000
FRONTEND_EVENT_LIMIT = 50
API_ACTIVITY_LIMIT = 20
NAVIGATION_LIMIT = 10
RUNTIME_ERROR_LIMIT = 10
STRING_MAX = 500


def sanitize_frontend_context(raw: Any) -> dict:
    """Normalize and redact ``frontend_context`` from the client."""
    if not isinstance(raw, dict):
        return {}
    cleaned = _sanitize_value(raw)
    if not isinstance(cleaned, dict):
        return {}
    return _clamp_size(cleaned)


def build_frontend_context_snapshot(
    frontend_context: dict | None = None,
    *,
    legacy_frontend_logs: list | None = None,
    draft_frontend_logs: list | None = None,
) -> dict:
    """Merge browser console lines into ``frontend_context.browser_console``."""
    ctx = sanitize_frontend_context(frontend_context) if frontend_context else {}
    existing = ctx.get('browser_console') if isinstance(ctx.get('browser_console'), list) else None
    console = merge_browser_console_entries(
        existing,
        draft_frontend_logs,
        legacy_frontend_logs,
    )
    if console:
        ctx['browser_console'] = console
    else:
        ctx.pop('browser_console', None)
    return _to_domain_snapshot(ctx)


def _to_domain_snapshot(ctx: dict) -> dict:
    """Best-effort coercion to the domain snapshot contract."""
    if not ctx:
        return {}
    try:
        return FrontendContextSnapshot.model_validate(ctx).model_dump(
            mode='json',
            exclude_none=True,
            exclude_defaults=True,
        )
    except Exception:
        return ctx


def _sanitize_value(value: Any, key_hint: str = '') -> Any:
    if value is None:
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if is_sensitive_key(key_hint):
            return '***'
        return redact_text_value(value, max_len=STRING_MAX)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        out: dict = {}
        for key, nested in value.items():
            key_str = str(key)
            if is_sensitive_key(key_str):
                out[key_str] = '***'
            else:
                out[key_str] = _sanitize_value(nested, key_str)
        return out
    return redact_text_value(str(value), max_len=STRING_MAX)


def _clamp_size(data: dict) -> dict:
    result = copy.deepcopy(data)

    events = result.get('recent_events')
    if isinstance(events, list) and len(events) > FRONTEND_EVENT_LIMIT:
        result['recent_events'] = events[-FRONTEND_EVENT_LIMIT:]

    api = result.get('recent_api_activity')
    if isinstance(api, list) and len(api) > API_ACTIVITY_LIMIT:
        result['recent_api_activity'] = api[-API_ACTIVITY_LIMIT:]

    nav = result.get('navigation')
    if isinstance(nav, dict):
        routes = nav.get('recent_routes')
        if isinstance(routes, list) and len(routes) > NAVIGATION_LIMIT:
            nav['recent_routes'] = routes[-NAVIGATION_LIMIT:]

    runtime = result.get('runtime')
    if isinstance(runtime, dict):
        errors = runtime.get('recent_errors')
        if isinstance(errors, list) and len(errors) > RUNTIME_ERROR_LIMIT:
            runtime['recent_errors'] = errors[-RUNTIME_ERROR_LIMIT:]

    console = result.get('browser_console')
    if isinstance(console, list) and len(console) > BROWSER_CONSOLE_LIMIT:
        result['browser_console'] = console[-BROWSER_CONSOLE_LIMIT:]

    encoded = json.dumps(result, ensure_ascii=False).encode('utf-8')
    if len(encoded) <= FRONTEND_CONTEXT_MAX_BYTES:
        return result

    shrunk = copy.deepcopy(result)
    for key in ('recent_events', 'recent_api_activity', 'browser_console'):
        items = shrunk.get(key)
        if isinstance(items, list) and len(items) > 5:
            shrunk[key] = items[-5:]
    if len(json.dumps(shrunk, ensure_ascii=False).encode('utf-8')) > FRONTEND_CONTEXT_MAX_BYTES:
        shrunk['truncated'] = True
    return shrunk
