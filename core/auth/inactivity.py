"""Idle timeout driven by ``TIME_INACTIVITY``.

The value is minutes. ``0``, a missing parameter, or an inactive one
disables the *reject* check. The activity clock still slides on every
authenticated request so turning the policy on later does not
mass-logout users whose ``last_activity_at`` was frozen while off.

Client reads the client/runtime catalog; admin reads the admin catalog.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from core.auth.refresh_service import parse_utc_timestamp

PARAM = 'TIME_INACTIVITY'
_CACHE_SECONDS = 30.0

logger = logging.getLogger('app.auth')

# (monotonic_ts, seconds) per user_type
_cached_windows: dict[str, tuple[float, int]] = {}


def clear_inactivity_cache() -> None:
    """Drop the process cache so tests and admin edits are visible at once."""
    _cached_windows.clear()


def inactivity_window_seconds(*, user_type: str = 'client') -> int:
    """Idle window in seconds. ``0`` means the reject policy is off."""
    key = 'admin' if user_type == 'admin' else 'client'
    now = time.monotonic()
    cached = _cached_windows.get(key)
    if cached is not None and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    seconds = _read_window_seconds(key)
    _cached_windows[key] = (now, seconds)
    return seconds


def inactivity_minutes(*, user_type: str = 'client') -> int:
    return inactivity_window_seconds(user_type=user_type) // 60


def _read_window_seconds(user_type: str) -> int:
    if user_type == 'admin':
        from core.admin_parameters import get_admin_parameter
        raw = get_admin_parameter(PARAM, default=0)
    else:
        from core.parameters import get_parameter
        raw = get_parameter(PARAM, default=0)
    try:
        minutes = int(raw or 0)
    except (TypeError, ValueError):
        logger.warning('Ignoring invalid %s value %r for %s', PARAM, raw, user_type)
        return 0
    if minutes <= 0:
        return 0
    return minutes * 60


def session_record_is_idle(
    record: dict | None,
    *,
    now: datetime | None = None,
    user_type: str = 'client',
) -> bool:
    """True when this refresh record has been quiet longer than the window.

    Records minted before the field existed are not idle: the next touch
    starts their clock. A disabled policy is never idle.
    """
    window = inactivity_window_seconds(user_type=user_type)
    if window <= 0 or not record:
        return False
    last = parse_utc_timestamp(record.get('last_activity_at'))
    if last is None:
        return False
    current = now or datetime.utcnow()
    return (current - last).total_seconds() >= window


def carried_last_activity(record: dict | None) -> str | None:
    """Activity timestamp a refresh rotation must keep.

    Copying it stops a silent access-token refresh from resetting the
    idle clock. ``None`` lets ``store()`` start the clock at issuance.
    """
    if not record:
        return None
    raw = record.get('last_activity_at')
    if isinstance(raw, str) and raw:
        return raw
    return None


def reject_idle_session(
    user_type: str,
    user_id,
    token_id,
    *,
    record: dict | None = None,
) -> bool:
    """Revoke and return True when this session is past the idle window.

    A missing record is not treated as idle: the caller already decided
    revocation. Always slides ``last_activity_at`` when the session is
    still live (even if the reject policy is off) so enabling the
    parameter later does not mass-logout active users.
    """
    if not token_id:
        return False
    from core.auth import refresh_service

    kind = 'admin' if user_type == 'admin' else 'client'
    current = record if record is not None else refresh_service.read_session(
        kind, user_id, token_id,
    )
    if not current:
        return False
    if session_record_is_idle(current, user_type=kind):
        refresh_service.revoke_session(kind, user_id, token_id)
        logger.info(
            'session_idle_revoked user_type=%s user_id=%s sid=%s',
            kind,
            user_id,
            token_id,
        )
        return True
    refresh_service.touch_session_activity(kind, user_id, token_id, current)
    return False


def reject_idle_client_session(
    user_id,
    token_id,
    *,
    record: dict | None = None,
) -> bool:
    """Compatibility wrapper for company-user idle rejection."""
    return reject_idle_session('client', user_id, token_id, record=record)


def reject_idle_admin_session(
    user_id,
    token_id,
    *,
    record: dict | None = None,
) -> bool:
    """Idle rejection for platform admin sessions."""
    return reject_idle_session('admin', user_id, token_id, record=record)
