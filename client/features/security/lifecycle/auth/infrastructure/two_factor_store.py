"""Backward-compatible re-export — implementation lives in ``core.auth``."""

from core.auth.two_factor_store import (  # noqa: F401
    delete,
    get,
    get_active_id,
    get_attempts,
    incr_attempts,
    put,
    replace_for_user,
)
