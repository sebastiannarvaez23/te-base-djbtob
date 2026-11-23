"""Strangler shim for portable trace + base JWT cookie actor binding."""

from necore.trace import *  # noqa: F401,F403
from necore.trace import (  # noqa: F401
    TXN_LOG_TRUNCATED,
    append_txn_log,
    drain_txn_logs,
    get_session_id,
    get_tenant,
    get_trace_id,
    get_user_id,
    get_username,
    is_txn_capturing,
    peek_txn_logs,
    set_session_id,
    set_tenant,
    set_trace_id,
    set_user_id,
    set_username,
    start_txn_capture,
    trace_block,
    trace_layer,
)


def bind_actor_from_request(request) -> None:
    """Rellena username/user_id desde ``request.user`` o cookies JWT (best-effort).

    Never hits the ORM: username comes from an authenticated Django user or from
    the ``username`` claim embedded in the access JWT.
    """
    try:
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            set_username(str(getattr(user, 'username', '') or ''))
            pk = getattr(user, 'pk', None) or getattr(user, 'id', None)
            set_user_id(str(pk) if pk is not None else '')
            return
    except Exception:
        pass
    _bind_actor_from_jwt_cookies(request)


def _bind_actor_from_jwt_cookies(request) -> None:
    """Resuelve actor desde access cookies sin pasar por DRF ni ORM."""
    try:
        from core.auth.cookies import ACCESS_ADMIN_COOKIE, ACCESS_CLIENT_COOKIE
        from core.auth.jwt_service import decode_access_token

        ctx = (request.META.get('HTTP_X_AUTH_CONTEXT') or '').lower()
        candidates: list[tuple[str, str]] = []
        if ctx == 'admin':
            candidates = [(ACCESS_ADMIN_COOKIE, 'admin')]
        elif ctx == 'client':
            candidates = [(ACCESS_CLIENT_COOKIE, 'client')]
        else:
            candidates = [
                (ACCESS_CLIENT_COOKIE, 'client'),
                (ACCESS_ADMIN_COOKIE, 'admin'),
            ]

        for cookie, expected_type in candidates:
            token = request.COOKIES.get(cookie)
            if not token:
                continue
            try:
                payload = decode_access_token(token)
            except Exception:
                continue
            if payload.get('user_type') != expected_type:
                continue
            user_id = str(payload.get('user_id') or '')
            if not user_id:
                continue
            set_user_id(user_id)
            set_username(str(payload.get('username') or '')[:150])
            return
    except Exception:
        pass
    set_username('')
    set_user_id('')
