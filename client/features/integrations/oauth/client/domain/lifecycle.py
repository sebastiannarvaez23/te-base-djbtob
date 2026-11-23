"""Integration Application status machine.

    ACTIVE ⇄ DISABLED
    ACTIVE | DISABLED → REVOKED   (terminal; secrets invalidated)
    REVOKED → deleted             (only revoked apps can be removed)

Each target maps to the statuses it may be reached from, so persistence can
apply the change as a single compare-and-set write.
"""
from __future__ import annotations

from core.errors import AppErrorCode, ConflictException

ACTIVE = 'ACTIVE'
DISABLED = 'DISABLED'
REVOKED = 'REVOKED'

MUTABLE_STATUSES: frozenset[str] = frozenset({ACTIVE, DISABLED})
DELETABLE_STATUSES: frozenset[str] = frozenset({REVOKED})

TRANSITION_SOURCES: dict[str, frozenset[str]] = {
    ACTIVE: frozenset({DISABLED}),
    DISABLED: frozenset({ACTIVE}),
    REVOKED: MUTABLE_STATUSES,
}


def ensure_mutable(status: str) -> None:
    if status not in MUTABLE_STATUSES:
        raise ConflictException(AppErrorCode.INT_OAUTH_APP_REVOKED)


def ensure_deletable(status: str) -> None:
    if status not in DELETABLE_STATUSES:
        raise ConflictException(AppErrorCode.INT_OAUTH_APP_NOT_REVOKED)
