"""Use cases for confirming a user's email address.

Tokens are opaque, single-use, and stored hashed.

  • Issue: caller passes the User; we generate a 32-byte url-safe token,
    store its sha256 hash, and return the raw token (only once).
  • Confirm: caller passes the raw token; we hash, look up, validate
    (not-used + not-expired), mark used, set ``user.email_verified_at``.

The throttling concern (avoid email-bombing the same user) lives in
the API layer because it's tied to HTTP semantics; the use case is
pure persistence + validation.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from core.errors import AppErrorCode, AuthException
from core.trace import trace_layer


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class IssueEmailConfirmationTokenUseCase:
    """Generate a fresh token for ``user``; supersedes any active ones."""

    def __init__(self, ttl_hours: int):
        self.ttl_hours = ttl_hours

    @trace_layer('application')
    def execute(self, user) -> str:
        from client.features.security.lifecycle.auth.models import EmailConfirmationToken

        # Single-shot semantics: invalidate any outstanding active tokens.
        EmailConfirmationToken.objects.filter(
            user=user, used_at__isnull=True,
        ).update(used_at=timezone.now())

        raw = secrets.token_urlsafe(32)
        EmailConfirmationToken.objects.create(
            user=user,
            token_hash=_hash_token(raw),
            expires_at=timezone.now() + timedelta(hours=self.ttl_hours),
        )
        return raw


class ConfirmEmailUseCase:
    """Validate ``raw_token`` and flip ``user.email_verified_at``."""

    @trace_layer('application')
    def execute(self, raw_token: str):
        from client.features.security.lifecycle.auth.models import EmailConfirmationToken

        record = (
            EmailConfirmationToken.objects
            .select_related('user')
            .filter(token_hash=_hash_token(raw_token))
            .first()
        )
        if record is None or not record.is_consumable():
            raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)

        now = timezone.now()
        record.used_at = now
        record.save(update_fields=['used_at'])

        user = record.user
        if user.email_verified_at is None:
            user.email_verified_at = now
            user.save(update_fields=['email_verified_at'])
        return user
