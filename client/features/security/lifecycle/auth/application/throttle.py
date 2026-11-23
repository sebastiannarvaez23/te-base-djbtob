"""Redis-backed throttle for email-confirmation resends,
password-recovery requests, and 2FA OTP resends.

Uses the 'auth' django-cache (Redis) with `cache.add`, which has
SET NX semantics — returns True only if the key was actually set.
That atomically enforces "one send per window" without races.

Windows are configured via runtime parameters:
  * ``EMAIL_CFM_WND_S`` (fallback 60s) — confirmation resend per user.
  * ``PWD_RESET_WND_S`` (fallback 60s) — password-reset request per user.
  * ``PWD_RESET_IP_WND_S`` (fallback 30s) — password-reset request per IP.
  * ``TWO_FA_WND_S`` (fallback 60s) — 2FA OTP resend per user.
"""

from django.core.cache import caches

from core.parameters import get_parameter


def _cache():
    return caches['auth']


def _window_seconds() -> int:
    return int(get_parameter('EMAIL_CFM_WND_S', default=60))


def try_acquire_resend_slot(user_id) -> bool:
    """Atomically reserve the resend slot for ``user_id``.

    Returns True when the caller is allowed to send (slot acquired);
    False when a previous send is still inside the throttle window.
    """
    key = f'email_confirm_throttle:{user_id}'
    return bool(_cache().add(key, '1', timeout=_window_seconds()))


def _recovery_user_window_seconds() -> int:
    return int(get_parameter('PWD_RESET_WND_S', default=60))


def _recovery_ip_window_seconds() -> int:
    return int(get_parameter('PWD_RESET_IP_WND_S', default=30))


def try_acquire_recovery_slot(user_id) -> bool:
    """Reserve the password-recovery slot for ``user_id``.

    Mitigates email-bombing the same account from multiple sources.
    """
    key = f'password_recovery_throttle:{user_id}'
    return bool(_cache().add(key, '1', timeout=_recovery_user_window_seconds()))


def try_acquire_recovery_ip_slot(ip: str) -> bool:
    """Reserve the password-recovery slot for ``ip``.

    Cuts brute-force enumeration attempts that iterate emails from the
    same origin. Empty/falsy IP allows the request (we don't block on
    missing telemetry).
    """
    if not ip:
        return True
    key = f'password_recovery_throttle_ip:{ip}'
    return bool(_cache().add(key, '1', timeout=_recovery_ip_window_seconds()))


def _two_factor_resend_window_seconds() -> int:
    return int(get_parameter('TWO_FA_WND_S', default=60))


def try_acquire_two_factor_resend_slot(user_id) -> bool:
    """Reserve the 2FA-email slot for ``user_id`` (one send per window)."""
    key = f'two_factor_resend_throttle:{user_id}'
    return bool(_cache().add(key, '1', timeout=_two_factor_resend_window_seconds()))
