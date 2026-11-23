"""Email OTP + trusted-device 2FA for client login.

Triggered only when ``DOUBLE_FA_AUTH`` is on *and* the presented device
serial is unknown (or missing). Password has already been verified by
the caller; these use cases never see credentials.

Security properties:
  * OTP is 6 cryptographically random digits, 5-minute TTL, 5 attempts.
  * Only HMAC-SHA256(challenge_id:otp, SECRET_KEY) is persisted.
  * Device serial is HMAC-bound to the user id so a stolen serial cannot
    be replayed against a different account.
  * Challenge ids are unguessable (32-byte url-safe).
"""

from __future__ import annotations

import hmac
import hashlib
import re
import secrets
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from client.features.security.lifecycle.auth.domain.schemas import (
    TrustedDeviceSchema,
    TwoFactorChallengeSchema,
    VerifiedTwoFactor,
)
from client.features.security.lifecycle.auth.infrastructure import two_factor_store
from core.auth.login_context import parse_device_label, resolve_login_location  # noqa: F401
from core.errors import AppErrorCode, AuthException, NotFoundException
from core.parameters import get_parameter
from platform.features.company.tenant.company.domain.lifecycle import CLOSED_LIFECYCLES
from core.trace import trace_layer

PARAM_CODE = 'DOUBLE_FA_AUTH'
OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_ATTEMPTS = 5
DEVICE_TTL_DAYS = 90
MAX_TRUSTED_DEVICES = 10
DEVICE_ID_RE = re.compile(r'^[A-Za-z0-9._-]{16,128}$')


def is_two_factor_enabled() -> bool:
    return bool(get_parameter(PARAM_CODE, default=False))


def _secret() -> bytes:
    return settings.SECRET_KEY.encode('utf-8')


def hash_otp(challenge_id: str, otp: str) -> str:
    msg = f'{challenge_id}:{otp}'.encode('utf-8')
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def hash_device(user_id, device_id: str) -> str:
    msg = f'device:{user_id}:{device_id}'.encode('utf-8')
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def generate_otp() -> str:
    return f'{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}'


def generate_challenge_id() -> str:
    return secrets.token_urlsafe(32)


def generate_device_serial() -> str:
    return secrets.token_urlsafe(32)


def mask_email(email: str) -> str:
    _, _, domain = (email or '').partition('@')
    if not domain:
        return '***'
    return f'***@{domain}'


def client_ip(request) -> str:
    meta = getattr(request, 'META', {}) or {}
    if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
        forwarded = meta.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return meta.get('REMOTE_ADDR') or ''


def _expires_in(payload: dict) -> int:
    raw = payload.get('expires_at')
    if not raw:
        return 0
    expires = parse_datetime(raw) if isinstance(raw, str) else raw
    if expires is None:
        return 0
    if timezone.is_naive(expires):
        expires = timezone.make_aware(expires, timezone.get_default_timezone())
    remaining = int((expires - timezone.now()).total_seconds())
    return max(0, remaining)


def _public_challenge(challenge_id: str, payload: dict) -> TwoFactorChallengeSchema:
    return TwoFactorChallengeSchema(
        two_factor_required=True,
        challenge_id=challenge_id,
        expires_in=_expires_in(payload),
        email_hint=payload.get('email_hint') or '***',
    )


def _normalize_device_id(device_id: Optional[str]) -> Optional[str]:
    value = (device_id or '').strip()
    if not value or not DEVICE_ID_RE.fullmatch(value):
        return None
    return value


def _live_payload(challenge_id: str) -> Optional[dict]:
    payload = two_factor_store.get(challenge_id)
    if payload is None:
        return None
    if _expires_in(payload) <= 0:
        two_factor_store.delete(challenge_id)
        return None
    return payload


def _ip_matches(stored: str, presented: str) -> bool:
    expected = (stored or '').strip()
    if not expected:
        return True
    return expected == (presented or '').strip()


class FindTrustedDeviceUseCase:
    """Return the active trusted-device row, or None if 2FA must run."""

    @trace_layer('application')
    def execute(self, user, device_id: Optional[str]):
        from client.features.security.lifecycle.auth.models import TrustedDevice

        serial = _normalize_device_id(device_id)
        if serial is None:
            return None

        cutoff = timezone.now() - timedelta(days=DEVICE_TTL_DAYS)
        return (
            TrustedDevice.objects
            .filter(
                user=user,
                device_hash=hash_device(user.pk, serial),
                revoked_at__isnull=True,
                last_used_at__gte=cutoff,
            )
            .first()
        )


class TouchTrustedDeviceUseCase:
    """Refresh last-seen telemetry after a password login on a known device."""

    @trace_layer('application')
    def execute(self, device, *, ip: str = '', user_agent: str = '') -> None:
        device.last_used_at = timezone.now()
        device.last_ip = ip or None
        device.last_ua = (user_agent or '')[:512]
        device.save(update_fields=['last_used_at', 'last_ip', 'last_ua'])


class RegisterTrustedDeviceUseCase:
    """Remember this serial after a successful OTP so the next login skips 2FA."""

    @trace_layer('application')
    def execute(self, user, device_id: Optional[str], *, ip: str = '', user_agent: str = '') -> None:
        from client.features.security.lifecycle.auth.models import TrustedDevice

        serial = _normalize_device_id(device_id)
        if serial is None:
            return

        now = timezone.now()
        digest = hash_device(user.pk, serial)
        label = parse_device_label(user_agent)

        with transaction.atomic():
            device, created = TrustedDevice.objects.select_for_update().get_or_create(
                user=user,
                device_hash=digest,
                defaults={
                    'label': label,
                    'last_ip': ip or None,
                    'last_ua': (user_agent or '')[:512],
                    'last_used_at': now,
                    'revoked_at': None,
                },
            )
            if not created:
                device.label = label or device.label
                device.last_ip = ip or None
                device.last_ua = (user_agent or '')[:512]
                device.last_used_at = now
                device.revoked_at = None
                device.save(update_fields=[
                    'label', 'last_ip', 'last_ua', 'last_used_at', 'revoked_at',
                ])

            active = list(
                TrustedDevice.objects
                .select_for_update()
                .filter(user=user, revoked_at__isnull=True)
                .order_by('last_used_at')
            )
            overflow = len(active) - MAX_TRUSTED_DEVICES
            if overflow > 0:
                now = timezone.now()
                for stale in active[:overflow]:
                    stale.revoked_at = now
                    stale.save(update_fields=['revoked_at'])


class IssueTwoFactorChallengeUseCase:
    """Create a Redis challenge and return ``(raw_otp, public_schema)``.

    The raw OTP is returned once so the caller can email it; it is never
    written to the store.
    """

    def __init__(self, ttl_minutes: int = OTP_TTL_MINUTES):
        self.ttl_minutes = ttl_minutes

    @trace_layer('application')
    def execute(
        self,
        user,
        *,
        ip: str = '',
        user_agent: str = '',
        remember_me: bool = False,
    ) -> Tuple[str, TwoFactorChallengeSchema]:
        challenge_id = generate_challenge_id()
        otp = generate_otp()
        now = timezone.now()
        expires_at = now + timedelta(minutes=self.ttl_minutes)
        payload = {
            'user_id': str(user.pk),
            'schema_name': connection.schema_name,
            'otp_hash': hash_otp(challenge_id, otp),
            'attempts': 0,
            'ip': ip or '',
            'user_agent': (user_agent or '')[:512],
            'email_hint': mask_email(getattr(user, 'email', '') or ''),
            'created_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'remember_me': bool(remember_me),
        }
        two_factor_store.replace_for_user(
            connection.schema_name,
            user.pk,
            challenge_id,
            payload,
            ttl_seconds=self.ttl_minutes * 60,
        )
        return otp, _public_challenge(challenge_id, payload)


class RotateTwoFactorChallengeUseCase:
    """Issue a fresh OTP for an existing (still-valid) challenge."""

    def __init__(self, ttl_minutes: int = OTP_TTL_MINUTES):
        self.ttl_minutes = ttl_minutes

    @trace_layer('application')
    def execute(self, challenge_id: str) -> Tuple[object, str, TwoFactorChallengeSchema]:
        payload = _live_payload(challenge_id)
        if payload is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)

        user = _load_challenge_user(payload)
        otp = generate_otp()
        now = timezone.now()
        expires_at = now + timedelta(minutes=self.ttl_minutes)
        payload['otp_hash'] = hash_otp(challenge_id, otp)
        payload['expires_at'] = expires_at.isoformat()
        two_factor_store.replace_for_user(
            payload.get('schema_name') or connection.schema_name,
            payload.get('user_id') or user.pk,
            challenge_id,
            payload,
            ttl_seconds=self.ttl_minutes * 60,
        )
        return user, otp, _public_challenge(challenge_id, payload)


class StampTwoFactorRememberMeUseCase:
    """Bind Remember-me to a live challenge (throttled reuse, no new email)."""

    @trace_layer('application')
    def execute(self, challenge_id: str, remember_me: bool) -> None:
        payload = _live_payload(challenge_id)
        if payload is None:
            return
        payload['remember_me'] = bool(remember_me)
        remaining = max(_expires_in(payload), 1)
        two_factor_store.put(challenge_id, payload, ttl_seconds=remaining)


class PeekTwoFactorChallengeUseCase:
    """Read-only public view of a live challenge (used when resend is throttled)."""

    @trace_layer('application')
    def execute(self, challenge_id: str) -> Tuple[object, TwoFactorChallengeSchema]:
        payload = _live_payload(challenge_id)
        if payload is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        user = _load_challenge_user(payload)
        return user, _public_challenge(challenge_id, payload)


class GetActiveTwoFactorChallengeUseCase:
    """Return the user's live challenge, or None if they must be issued a new one."""

    @trace_layer('application')
    def execute(self, user) -> Optional[TwoFactorChallengeSchema]:
        challenge_id = two_factor_store.get_active_id(connection.schema_name, user.pk)
        if not challenge_id:
            return None
        payload = _live_payload(challenge_id)
        if payload is None:
            return None
        return _public_challenge(challenge_id, payload)


class VerifyTwoFactorChallengeUseCase:
    """Consume a challenge with the presented OTP. Returns the user on success."""

    @trace_layer('application')
    def execute(self, challenge_id: str, otp_code: str, *, ip: str = '') -> VerifiedTwoFactor:
        payload = _live_payload(challenge_id)
        if payload is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)

        if not _ip_matches(payload.get('ip') or '', ip):
            two_factor_store.delete(challenge_id)
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)

        presented = (otp_code or '').strip()
        expected = payload.get('otp_hash') or ''
        candidate = hash_otp(challenge_id, presented)
        if len(expected) != len(candidate) or not hmac.compare_digest(candidate, expected):
            remaining_ttl = _expires_in(payload)
            attempts = two_factor_store.incr_attempts(challenge_id, remaining_ttl)
            if attempts >= MAX_ATTEMPTS or remaining_ttl <= 0:
                two_factor_store.delete(challenge_id)
                raise AuthException(AppErrorCode.AUTH_OTP_LOCKED)
            raise AuthException(AppErrorCode.AUTH_OTP_INVALID)

        two_factor_store.delete(challenge_id)
        return VerifiedTwoFactor(
            user=_load_challenge_user(payload),
            remember_me=bool(payload.get('remember_me')),
        )


class ListTrustedDevicesUseCase:

    @trace_layer('application')
    def execute(self, user, current_serial: Optional[str] = None) -> list[TrustedDeviceSchema]:
        from client.features.security.lifecycle.auth.models import TrustedDevice

        cutoff = timezone.now() - timedelta(days=DEVICE_TTL_DAYS)
        current_hash = (
            hash_device(user.pk, current_serial)
            if _normalize_device_id(current_serial)
            else None
        )
        rows = (
            TrustedDevice.objects
            .filter(user=user, revoked_at__isnull=True, last_used_at__gte=cutoff)
            .order_by('-last_used_at')
        )
        return [
            TrustedDeviceSchema(
                id=str(row.id),
                label=row.label or 'Unknown',
                last_ip=row.last_ip,
                last_used_at=row.last_used_at.isoformat(),
                created_at=row.created_at.isoformat(),
                is_current=bool(current_hash and row.device_hash == current_hash),
            )
            for row in rows
        ]


class RevokeTrustedDeviceUseCase:

    @trace_layer('application')
    def execute(self, user, device_id) -> str:
        from client.features.security.lifecycle.auth.models import TrustedDevice

        row = TrustedDevice.objects.filter(
            pk=device_id,
            user=user,
            revoked_at__isnull=True,
        ).first()
        if row is None:
            raise NotFoundException(AppErrorCode.AUTH_DEVICE_NOT_FOUND)
        row.revoked_at = timezone.now()
        row.save(update_fields=['revoked_at'])
        return row.device_hash


def _load_challenge_user(payload: dict):
    stored_schema = payload.get('schema_name')
    if stored_schema and stored_schema != connection.schema_name:
        raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)

    User = get_user_model()
    try:
        user = User.objects.select_related('company').get(pk=payload.get('user_id'))
    except (User.DoesNotExist, ValueError, TypeError):
        raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)

    lifecycle = getattr(getattr(user, 'company', None), 'lifecycle', None) or 'ACTIVE'
    if lifecycle in CLOSED_LIFECYCLES:
        raise AuthException(AppErrorCode.AUTH_COMPANY_CLOSED)
    if not user.is_active:
        raise AuthException(AppErrorCode.AUTH_ACCOUNT_INACTIVE)
    return user
