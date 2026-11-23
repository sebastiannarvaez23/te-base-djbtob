"""Password history (HISTORY_PASS) and expiry (PASSWORD_EXPIRED) policy.

``HISTORY_PASS`` may be BOOL (on → last 5 passwords) or INT (explicit depth).
``PASSWORD_EXPIRED`` is days until a password must be changed; ``0`` / false
disables expiry.
"""

from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from core.errors import AppErrorCode, AuthException
from core.parameters import get_parameter

HISTORY_PARAM = 'HISTORY_PASS'
EXPIRY_PARAM = 'PASSWORD_EXPIRED'
_HISTORY_ON_DEFAULT = 5
_EXPIRY_ON_DEFAULT = 90


def history_limit() -> int:
    return _policy_int(HISTORY_PARAM, enabled_default=_HISTORY_ON_DEFAULT)


def expiry_days() -> int:
    return _policy_int(EXPIRY_PARAM, enabled_default=_EXPIRY_ON_DEFAULT)


def is_password_expired(user) -> bool:
    days = expiry_days()
    if days <= 0:
        return False
    changed = getattr(user, 'password_changed_at', None)
    if changed is None:
        return False
    return timezone.now() >= changed + timedelta(days=days)


def start_password_clock(user) -> None:
    """Stamp ``password_changed_at`` on first login after expiry policy is on.

    Existing accounts have a NULL timestamp (the field is new). Without a
    stamp they would never expire; locking them out on first login would
    force a mass password reset. Starting the clock here gives them a full
    ``PASSWORD_EXPIRED`` window from the next successful authentication.
    """
    if getattr(user, 'password_changed_at', None) is not None:
        return
    if expiry_days() <= 0:
        return
    user.password_changed_at = timezone.now()
    if getattr(user, 'pk', None):
        user.save(update_fields=['password_changed_at'])


def rotate_password(user, new_password: str, *, save: bool = True) -> None:
    """Reject reuse, archive the current hash, then set the new password.

    The current password is always rejected (even when ``HISTORY_PASS`` is 0)
    so an expiry-forced change cannot reset the clock with the same secret.
    """
    if _usable_hash(user) and check_password(new_password, user.password):
        raise AuthException(AppErrorCode.AUTH_PASSWORD_REUSED)
    if _usable_hash(user):
        _reject_if_reused(user, new_password)
        if getattr(user, 'pk', None) and history_limit() > 0:
            _archive_current(user)
    user.set_password(new_password)
    user.password_changed_at = timezone.now()
    if save and getattr(user, 'pk', None):
        user.save(update_fields=['password', 'password_changed_at'])


def _policy_int(code: str, *, enabled_default: int) -> int:
    raw = get_parameter(code, default=0)
    if raw is True:
        return enabled_default
    if raw is False or raw is None:
        return 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def _usable_hash(user) -> bool:
    stored = getattr(user, 'password', None)
    if not stored or not isinstance(stored, str):
        return False
    return not stored.startswith('!')


def _reject_if_reused(user, new_password: str) -> None:
    limit = history_limit()
    if limit <= 0:
        return
    hashes = []
    if _usable_hash(user):
        hashes.append(user.password)
    extra = limit - len(hashes)
    if extra > 0 and getattr(user, 'pk', None):
        from client.features.security.lifecycle.auth.models import PasswordHistory
        hashes.extend(
            PasswordHistory.objects
            .filter(user=user)
            .order_by('-created_at')
            .values_list('password_hash', flat=True)[:extra]
        )
    for stored in hashes[:limit]:
        if stored and check_password(new_password, stored):
            raise AuthException(AppErrorCode.AUTH_PASSWORD_REUSED)


def _archive_current(user) -> None:
    if not _usable_hash(user):
        return
    from client.features.security.lifecycle.auth.models import PasswordHistory

    PasswordHistory.objects.create(user=user, password_hash=user.password)
    keep = max(history_limit() - 1, 0)
    stale_ids = list(
        PasswordHistory.objects
        .filter(user=user)
        .order_by('-created_at')
        .values_list('id', flat=True)[keep:]
    )
    if stale_ids:
        PasswordHistory.objects.filter(id__in=stale_ids).delete()
