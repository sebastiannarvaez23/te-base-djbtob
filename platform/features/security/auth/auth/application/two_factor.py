"""Email OTP + trusted-device 2FA for admin login (DOUBLE_FA_AUTH)."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.admin_parameters import get_admin_parameter
from core.auth import two_factor_store
from core.errors import AppErrorCode, AuthException
from core.trace import trace_layer
from platform.features.security.auth.auth.domain.interfaces import (
    IAdminTrustedDeviceRepository,
    IAdminUserLookup,
)
from platform.features.security.auth.auth.domain.schemas import (
    AdminTwoFactorChallengeSchema,
    AdminVerifiedTwoFactor,
)

PARAM_CODE = 'DOUBLE_FA_AUTH'
OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_ATTEMPTS = 5
DEVICE_TTL_DAYS = 90
MAX_TRUSTED_DEVICES = 10
DEVICE_ID_RE = re.compile(r'^[A-Za-z0-9._-]{16,128}$')
_SCHEMA = 'admin'


def is_two_factor_enabled() -> bool:
    return bool(get_admin_parameter(PARAM_CODE, default=False))


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


def _public_challenge(challenge_id: str, payload: dict) -> AdminTwoFactorChallengeSchema:
    return AdminTwoFactorChallengeSchema(
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


class FindAdminTrustedDeviceUseCase:
    def __init__(self, devices: IAdminTrustedDeviceRepository):
        self.devices = devices

    @trace_layer('application')
    def execute(self, user, device_id: Optional[str]):
        serial = _normalize_device_id(device_id)
        if serial is None:
            return None
        cutoff = timezone.now() - timedelta(days=DEVICE_TTL_DAYS)
        return self.devices.find_active(
            user, hash_device(user.pk, serial), cutoff=cutoff,
        )


class TouchAdminTrustedDeviceUseCase:
    def __init__(self, devices: IAdminTrustedDeviceRepository):
        self.devices = devices

    @trace_layer('application')
    def execute(self, device, *, ip: str = '', user_agent: str = '') -> None:
        self.devices.touch(device, ip=ip, user_agent=user_agent)


class RegisterAdminTrustedDeviceUseCase:
    def __init__(self, devices: IAdminTrustedDeviceRepository):
        self.devices = devices

    @trace_layer('application')
    def execute(self, user, device_id: str, *, ip: str = '', user_agent: str = '') -> None:
        serial = _normalize_device_id(device_id)
        if serial is None:
            return
        self.devices.register(
            user,
            hash_device(user.pk, serial),
            ip=ip,
            user_agent=user_agent,
            max_devices=MAX_TRUSTED_DEVICES,
        )


class IssueAdminTwoFactorChallengeUseCase:
    @trace_layer('application')
    def execute(
        self, user, *, ip: str = '', user_agent: str = '',
    ) -> Tuple[str, AdminTwoFactorChallengeSchema]:
        challenge_id = generate_challenge_id()
        otp = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=OTP_TTL_MINUTES)
        payload = {
            'user_id': str(user.pk),
            'schema_name': _SCHEMA,
            'otp_hash': hash_otp(challenge_id, otp),
            'email_hint': mask_email(getattr(user, 'email', '') or ''),
            'ip': ip or '',
            'user_agent': (user_agent or '')[:512],
            'expires_at': expires_at.isoformat(),
        }
        two_factor_store.replace_for_user(
            _SCHEMA, user.pk, challenge_id, payload, OTP_TTL_MINUTES * 60,
        )
        return otp, _public_challenge(challenge_id, payload)


class GetActiveAdminTwoFactorChallengeUseCase:
    @trace_layer('application')
    def execute(self, user) -> Optional[AdminTwoFactorChallengeSchema]:
        challenge_id = two_factor_store.get_active_id(_SCHEMA, user.pk)
        if not challenge_id:
            return None
        payload = _live_payload(challenge_id)
        if payload is None:
            return None
        return _public_challenge(challenge_id, payload)


class PeekAdminTwoFactorChallengeUseCase:
    def __init__(self, users: IAdminUserLookup):
        self.users = users

    @trace_layer('application')
    def execute(self, challenge_id: str):
        payload = _live_payload(challenge_id)
        if payload is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        user = self.users.get_active_by_id(payload['user_id'])
        if user is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        return user, _public_challenge(challenge_id, payload)


class RotateAdminTwoFactorChallengeUseCase:
    def __init__(self, users: IAdminUserLookup):
        self.users = users

    @trace_layer('application')
    def execute(self, challenge_id: str):
        payload = _live_payload(challenge_id)
        if payload is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        user = self.users.get_active_by_id(payload['user_id'])
        if user is None:
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        otp, challenge = IssueAdminTwoFactorChallengeUseCase().execute(
            user,
            ip=payload.get('ip') or '',
            user_agent=payload.get('user_agent') or '',
        )
        return user, otp, challenge


def _ip_matches(stored: str, presented: str) -> bool:
    expected = (stored or '').strip()
    if not expected:
        return True
    return expected == (presented or '').strip()


class VerifyAdminTwoFactorChallengeUseCase:
    def __init__(self, users: IAdminUserLookup):
        self.users = users

    @trace_layer('application')
    def execute(self, challenge_id: str, otp_code: str, *, ip: str = '') -> AdminVerifiedTwoFactor:
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
            attempts = two_factor_store.incr_attempts(challenge_id, remaining_ttl or 1)
            if attempts >= MAX_ATTEMPTS or remaining_ttl <= 0:
                two_factor_store.delete(challenge_id)
                raise AuthException(AppErrorCode.AUTH_OTP_LOCKED)
            raise AuthException(AppErrorCode.AUTH_OTP_INVALID)

        user = self.users.get_active_by_id(payload['user_id'], with_role=True)
        if user is None:
            two_factor_store.delete(challenge_id)
            raise AuthException(AppErrorCode.AUTH_OTP_EXPIRED)
        two_factor_store.delete(challenge_id)
        return AdminVerifiedTwoFactor(user=user)
