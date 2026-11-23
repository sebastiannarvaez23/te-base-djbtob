"""Detect operator orientation questions (where am I / which module / tab)."""

from __future__ import annotations

import re

_ORIENTATION_RE = re.compile(
    r'(?i)'
    r'(?:'
    r'd[oó]nde\s+(?:estoy|me\s+encuentro)|'
    r'en\s+qu[eé]\s+(?:pantalla|m[oó]dulo|pesta[nñ]a|secci[oó]n|p[aá]gina)|'
    r'qu[eé]\s+(?:pantalla|m[oó]dulo|pesta[nñ]a|secci[oó]n)|'
    r'para\s+qu[eé]\s+sirve|'
    r'where\s+am\s+i|'
    r'which\s+(?:screen|module|tab|page|section)|'
    r'what\s+(?:screen|module|tab|page|section)|'
    r'current\s+(?:screen|module|tab|page)|'
    r'what\s+is\s+this\s+(?:module|screen|tab|page)\s+for|'
    r'what\s+is\s+this\s+(?:module|screen|tab)\s+used\s+for'
    r')',
)


def is_orientation_question(message: str) -> bool:
    """True when the user asks where they are or what the screen/module/tab is for."""
    text = (message or '').strip()
    if not text:
        return False
    return bool(_ORIENTATION_RE.search(text))
