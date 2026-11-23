"""Normalize Django template source before render.

Pretty-printed HTML in the admin often splits ``{{ variable }}`` across
newlines. Django's lexer does not treat those as variable tags (``.`` does
not match ``\\n``), so the literal ``{{ user_name }}`` leaks into the email.
"""
from __future__ import annotations

import re

_VAR_TAG_RE = re.compile(r'\{\{(.*?)\}\}', re.DOTALL)
_BLOCK_TAG_RE = re.compile(r'\{%(.*?)%\}', re.DOTALL)


def normalize_django_template_source(source: str) -> str:
    """Collapse whitespace inside ``{{ }}`` / ``{% %}`` so tags stay valid."""
    if not source:
        return source

    def _collapse(match: re.Match[str], opener: str, closer: str) -> str:
        inner = ' '.join(match.group(1).split())
        if not inner:
            return f'{opener}{closer}'
        return f'{opener} {inner} {closer}'

    collapsed = _VAR_TAG_RE.sub(lambda m: _collapse(m, '{{', '}}'), source)
    return _BLOCK_TAG_RE.sub(lambda m: _collapse(m, '{%', '%}'), collapsed)
