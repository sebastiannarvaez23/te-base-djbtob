"""Use cases for the password-recovery flow.

Mirrors the email-confirmation token mechanics: opaque token, sha256
in storage, single-use, expiring. Three use cases:

  * Issue   — invalidates any active token for the user and emits a new one.
  * Validate— pure read; returns the user if the token is consumable.
  * Consume — validates + rotates the password atomically and marks used.

The HTTP/throttling concerns live in the API layer; these use cases are
pure persistence + validation.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from core.errors import AppErrorCode, AuthException
from core.trace import trace_layer


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class IssuePasswordRecoveryTokenUseCase:
    """Generate a fresh recovery token for ``user``; supersedes active ones."""

    def __init__(self, ttl_minutes: int):
        self.ttl_minutes = ttl_minutes

    @trace_layer('application')
    def execute(self, user, request_ip: Optional[str] = None, request_ua: str = '') -> str:
        from client.features.security.lifecycle.auth.models import PasswordRecoveryToken

        PasswordRecoveryToken.objects.filter(
            user=user, used_at__isnull=True,
        ).update(used_at=timezone.now())

        raw = secrets.token_urlsafe(32)
        PasswordRecoveryToken.objects.create(
            user=user,
            token_hash=_hash_token(raw),
            request_ip=request_ip or None,
            request_ua=(request_ua or '')[:512],
            expires_at=timezone.now() + timedelta(minutes=self.ttl_minutes),
        )
        return raw


class ValidatePasswordRecoveryTokenUseCase:
    """Return the owning user if ``raw_token`` is consumable; raise otherwise.

    Does not mutate state — safe to call from a pre-form validation endpoint.
    """

    @trace_layer('application')
    def execute(self, raw_token: str):
        from client.features.security.lifecycle.auth.models import PasswordRecoveryToken

        record = (
            PasswordRecoveryToken.objects
            .select_related('user')
            .filter(token_hash=_hash_token(raw_token))
            .first()
        )
        if record is None or not record.is_consumable():
            raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)
        if not record.user.is_active:
            raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)
        return record.user


class ConsumePasswordRecoveryTokenUseCase:
    """Rotate the user's password and burn the token. Returns the user."""

    @trace_layer('application')
    def execute(self, raw_token: str, new_password: str):
        from client.features.security.lifecycle.auth.models import PasswordRecoveryToken

        with transaction.atomic():
            record = (
                PasswordRecoveryToken.objects
                .select_for_update()
                .select_related('user')
                .filter(token_hash=_hash_token(raw_token))
                .first()
            )
            if record is None or not record.is_consumable():
                raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)

            user = record.user
            if not user.is_active:
                raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)

            now = timezone.now()
            record.used_at = now
            record.save(update_fields=['used_at'])

            from client.features.security.lifecycle.auth.application.password_policy import rotate_password
            rotate_password(user, new_password)

        return user
