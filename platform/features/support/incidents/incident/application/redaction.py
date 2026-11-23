"""Shared redaction helpers for incident frontend evidence."""
from __future__ import annotations

import re

from core.logging_redaction import inline_json

SENSITIVE_KEY = re.compile(
    r'password|token|secret|authorization|cookie|api[_-]?key|refresh|access|jwt|bearer',
    re.IGNORECASE,
)
SECRET_PAIR = re.compile(
    r'(?i)\b(password|token|secret|authorization|api_key|refresh|access|jwt|cookie)\s*[:=]\s*\S+',
)


def is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_KEY.search(key or ''))


def redact_secret_pairs(text: str) -> str:
    return SECRET_PAIR.sub(r'\1=***', text or '')


def redact_text_value(text: str, *, max_len: int) -> str:
    stripped = (text or '').strip()
    if not stripped:
        return ''
    if stripped.startswith('{') or stripped.startswith('['):
        return inline_json(stripped)[:max_len]
    return redact_secret_pairs(stripped)[:max_len]
