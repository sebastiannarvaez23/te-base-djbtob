"""Persistent auth artefacts.

JWT access tokens are stateless and refresh tokens live in Redis,
but single-use email-confirmation tokens need durability and audit
trail, so they live here.
"""


from django.conf import settings
from django.db import models
from django.utils import timezone

from core.ids import uuid7


class EmailConfirmationToken(models.Model):
    """Single-use, hashed token that confirms a user's email address.

    The raw token is sent only by email; only its sha256 hash is stored.
    A token is consumable while ``used_at IS NULL`` and ``expires_at > now``.
    Issuing a new token does NOT delete previous active ones — the consume
    path marks them as used to enforce single-shot semantics.
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_confirmation_tokens',
    )
    # sha256 hex digest, fixed 64 chars.
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'security_email_confirmation_tokens'
        verbose_name = 'Email confirmation token'
        verbose_name_plural = 'Email confirmation tokens'
        indexes = [
            # Most lookups are by hash; secondary index for the resend path
            # (latest active token per user).
            models.Index(fields=['user', 'used_at']),
        ]

    def is_consumable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class PasswordRecoveryToken(models.Model):
    """Single-use, hashed token that authorizes a password reset.

    Same persistence rules as ``EmailConfirmationToken``: only the sha256
    hash of the raw token is stored; the raw value lives just in the
    outbound email. ``request_ip`` and ``request_ua`` are kept for audit
    so an abuse pattern can be traced even after the token is consumed.
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_recovery_tokens',
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    request_ua = models.CharField(max_length=512, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'security_password_recovery_tokens'
        verbose_name = 'Password recovery token'
        verbose_name_plural = 'Password recovery tokens'
        indexes = [
            models.Index(fields=['user', 'used_at']),
        ]

    def is_consumable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class TrustedDevice(models.Model):
    """A browser/device the user has already completed 2FA on.

    The client holds a high-entropy serial in localStorage and sends it on
    login. Only the HMAC-SHA256 of ``(user_id, serial)`` is stored here, so a
    database leak cannot reconstruct the serial or reuse it for another user.

    A device stays trusted while ``revoked_at`` is null and ``last_used_at``
    is inside the inactivity window enforced by the use case (not a DB
    constraint — that window is a runtime policy).
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trusted_devices',
    )
    device_hash = models.CharField(max_length=64)
    label = models.CharField(max_length=64, blank=True, default='')
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_ua = models.CharField(max_length=512, blank=True, default='')
    last_used_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'security_trusted_devices'
        verbose_name = 'Trusted device'
        verbose_name_plural = 'Trusted devices'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_hash'],
                name='uniq_trusted_device_user_hash',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'revoked_at'], name='sec_tdev_user_revoked_idx'),
        ]


class PasswordHistory(models.Model):
    """Previous password hashes for HISTORY_PASS reuse checks.

    Only Django hasher strings are stored — never the raw password.
    Rows older than the current ``HISTORY_PASS`` window are pruned on rotate.
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_history',
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'security_password_history'
        verbose_name = 'Password history'
        verbose_name_plural = 'Password history'
        indexes = [
            models.Index(fields=['user', '-created_at'], name='sec_pwdhist_user_created_idx'),
        ]
