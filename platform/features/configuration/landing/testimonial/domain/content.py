"""Canonical quote bytes hashed before the HMAC seal."""

from __future__ import annotations

import json
from uuid import UUID

DOCUMENT_TYPE = 'testimonial'


def canonical_quote(
    *,
    author_id: UUID,
    score: int,
    message: str,
    locale: str,
) -> str:
    """Stable JSON of the words the author attests to."""
    return json.dumps(
        {
            'author_id': str(author_id),
            'locale': locale,
            'message': message,
            'score': score,
        },
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    )
