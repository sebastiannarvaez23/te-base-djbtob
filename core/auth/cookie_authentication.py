"""DRF authentication classes based on JWT access tokens and refresh tokens
stored in HttpOnly cookies.

Access tokens (JWT):
    Validated by cryptographic signature + expiration.  No database lookup.

Refresh tokens (opaque):
    Used exclusively by the refresh endpoints. Validated against Redis.

Context header
--------------
The frontend sends ``X-Auth-Context: admin|client`` on every API call so
that, when both admin and client cookies are present (same browser), the
backend only attempts the authentication class that matches the caller's
context.  If the header is missing, authentication proceeds normally.
"""
import jwt as pyjwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.auth.cookies import (
    ACCESS_ADMIN_COOKIE,
    ACCESS_CLIENT_COOKIE,
    REFRESH_ADMIN_COOKIE,
    REFRESH_CLIENT_COOKIE,
)
from core.auth.inactivity import (
    reject_idle_admin_session,
    reject_idle_client_session,
    session_record_is_idle,
)
from core.auth.jwt_service import decode_access_token
from core.auth import refresh_service
from core.auth.refresh_service import read_session
from core.errors import AppErrorCode, AuthException


def _auth_context(request) -> str | None:
    """Return the value of X-Auth-Context (lowered) or None."""
    value = request.META.get('HTTP_X_AUTH_CONTEXT', '')
    return value.lower() or None


_PAYLOAD_UNSET = object()


def client_access_payload(request) -> dict | None:
    """Decode the client access cookie once per request.

    Returns the JWT payload when it is a valid client token, otherwise None.
    Middlewares that run before DRF authentication share this result instead
    of verifying the same signature on every layer.
    """
    cached = getattr(request, '_wa_client_access_payload', _PAYLOAD_UNSET)
    if cached is not _PAYLOAD_UNSET:
        return cached

    from core.auth.cookies import ACCESS_CLIENT_COOKIE

    cookies = getattr(request, 'COOKIES', None) or {}
    raw = cookies.get(ACCESS_CLIENT_COOKIE) if hasattr(cookies, 'get') else None
    payload = None
    if raw:
        try:
            decoded = decode_access_token(raw)
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            decoded = None
        if isinstance(decoded, dict) and decoded.get('user_type') == 'client':
            payload = decoded
    try:
        request._wa_client_access_payload = payload
    except Exception:
        pass
    return payload


def _path_allows_closed_company_session(request) -> bool:
    """Self-close reason + logout must still work after CLOSE (grace > 0)."""
    path = getattr(request, 'path', None)
    if not isinstance(path, str):
        return False
    normalized = path.rstrip('/') + '/'
    return normalized.endswith('/close/complete/') or normalized.endswith('/auth/logout/')


def _reject_closed_company_session(request, user) -> None:
    """Reject JWTs once the tenant is pending purge or gone (AUTH_019).

    CLOSED is left open for the spared self-close actor so they can finish
    ``/close/complete/`` (and incidental polling) during grace days.
    Immediate deregistration (0 days) deactivates the actor and purges, so
    the next request fails as inactive or hits GONE here.
    """
    if _path_allows_closed_company_session(request):
        return
    company = getattr(user, 'company', None)
    lifecycle = getattr(company, 'lifecycle', None) if company is not None else None
    if not isinstance(lifecycle, str):
        return
    from platform.features.company.tenant.company.domain.lifecycle import (
        LIFECYCLE_GONE,
        LIFECYCLE_PENDING_PURGE,
    )
    if lifecycle not in (LIFECYCLE_GONE, LIFECYCLE_PENDING_PURGE):
        return
    from core.errors import AppErrorCode, AuthException
    raise AuthException(AppErrorCode.AUTH_COMPANY_CLOSED)


def get_client_user(request, user_id):
    """Load the active client user once per request.

    SubscriptionMiddleware and JWTAccessAuthentication share the same row
    (role, company, location) instead of querying ``registration_user`` twice.
    """
    if getattr(request, '_wa_client_user_loaded', False) is True:
        return getattr(request, '_wa_client_user', None)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.select_related(
            'rol',
            'company',
            'company__geo_city__department__country',
        ).get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        user = None
    try:
        request._wa_client_user = user
        request._wa_client_user_loaded = True
    except Exception:
        pass
    return user


# ── JWT Access Token Authentication ──────────────────────────────────────────


class JWTAccessAuthentication(BaseAuthentication):
    """Authenticate client (tenant) users via JWT in the `access_client` cookie."""

    def authenticate(self, request):
        # If the caller explicitly declares an admin context, skip client auth.
        if _auth_context(request) == 'admin':
            return None

        token = request.COOKIES.get(ACCESS_CLIENT_COOKIE)
        if not token:
            return None
        try:
            payload = decode_access_token(token)
        except pyjwt.ExpiredSignatureError:
            raise AuthenticationFailed('Session expired.')
        except pyjwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid session.')

        if payload.get('user_type') != 'client':
            return None  # Not a client token — let next authenticator try

        # One Redis GET: existence + idle clock (avoids session_exists + read).
        # Tokens without 'sid' (legacy) are rejected — the interceptor refreshes.
        sid = payload.get('sid')
        record = read_session('client', payload['user_id'], sid) if sid else None
        if not sid or record is None:
            raise AuthenticationFailed('Session revoked.')
        if reject_idle_client_session(payload['user_id'], sid, record=record):
            raise AuthException(AppErrorCode.AUTH_SESSION_IDLE)

        user = get_client_user(request, payload['user_id'])
        if user is None:
            raise AuthenticationFailed('User not found or inactive.')

        rol = getattr(user, 'rol', None)
        if rol is None or not getattr(rol, 'is_active', False):
            raise AuthenticationFailed('User role is inactive.')

        # Universal roles can be disabled per company via CompanyRolAccess.
        if getattr(rol, 'company_id', None) is None and getattr(user, 'company_id', None):
            from client.features.security.lifecycle.registration.models import CompanyRolAccess
            access = (
                CompanyRolAccess.objects
                .filter(company_id=user.company_id, rol_id=rol.id)
                .only('is_active')
                .first()
            )
            if access is not None and not access.is_active:
                raise AuthenticationFailed('User role is inactive for this company.')

        _reject_closed_company_session(request, user)
        return user, payload


class JWTAdminAccessAuthentication(BaseAuthentication):
    """Authenticate platform admins via JWT in the `access_admin` cookie."""

    def authenticate(self, request):
        # If the caller explicitly declares a client context, skip admin auth.
        if _auth_context(request) == 'client':
            return None

        token = request.COOKIES.get(ACCESS_ADMIN_COOKIE)
        if not token:
            return None
        try:
            payload = decode_access_token(token)
        except pyjwt.ExpiredSignatureError:
            raise AuthenticationFailed('Admin session expired.')
        except pyjwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid admin session.')

        if payload.get('user_type') != 'admin':
            return None

        # One Redis GET: existence + idle clock (mirrors client auth).
        sid = payload.get('sid')
        record = read_session('admin', payload['user_id'], sid) if sid else None
        if not sid or record is None:
            raise AuthenticationFailed('Admin session revoked.')
        if reject_idle_admin_session(payload['user_id'], sid, record=record):
            raise AuthException(AppErrorCode.AUTH_SESSION_IDLE)

        from platform.features.security.identity.users.models import AdminUser
        try:
            user = AdminUser.objects.select_related('role').get(
                pk=payload['user_id'], is_active=True,
            )
        except AdminUser.DoesNotExist:
            raise AuthenticationFailed('Admin user not found or inactive.')

        role = getattr(user, 'role', None)
        if role is None or not getattr(role, 'is_active', False):
            raise AuthenticationFailed('Admin role is inactive.')

        return user, payload


# ── Refresh Token Authentication ─────────────────────────────────────────────


class RefreshTokenAuthentication(BaseAuthentication):
    """Authenticate via the `refresh_client` cookie.

    Used **only** by the client refresh endpoint.
    Validates the opaque refresh token against Redis.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(REFRESH_CLIENT_COOKIE)
        if not raw_token:
            return None

        record = refresh_service.validate(raw_token, expected_type='client')
        if record is None:
            raise AuthenticationFailed('Invalid or expired refresh token.')
        if session_record_is_idle(record):
            refresh_service.revoke(raw_token, user_type='client')
            raise AuthException(AppErrorCode.AUTH_SESSION_IDLE)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.select_related(
                'rol',
                'company',
                'company__geo_city__department__country',
            ).get(
                pk=record['user_id'], is_active=True,
            )
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found or inactive.')

        _reject_closed_company_session(request, user)
        # Attach the raw refresh token and record for the view to use
        request._refresh_token_raw = raw_token
        request._refresh_record = record
        return user, record


class AdminRefreshTokenAuthentication(BaseAuthentication):
    """Authenticate via the `refresh_admin` cookie.

    Used **only** by the admin refresh endpoint.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(REFRESH_ADMIN_COOKIE)
        if not raw_token:
            return None

        record = refresh_service.validate(raw_token, expected_type='admin')
        if record is None:
            raise AuthenticationFailed('Invalid or expired admin refresh token.')
        if session_record_is_idle(record, user_type='admin'):
            refresh_service.revoke(raw_token, user_type='admin')
            raise AuthException(AppErrorCode.AUTH_SESSION_IDLE)

        from platform.features.security.identity.users.models import AdminUser
        try:
            user = AdminUser.objects.select_related('role').get(
                pk=record['user_id'], is_active=True,
            )
        except AdminUser.DoesNotExist:
            raise AuthenticationFailed('Admin user not found or inactive.')

        request._refresh_token_raw = raw_token
        request._refresh_record = record
        return user, record


# ── Backwards-compatible aliases ─────────────────────────────────────────────
# These are referenced by old cookie names in some files. Keep as aliases
# pointing to the new JWT classes until all references are cleaned up.

CookieAdminTokenAuthentication = JWTAdminAccessAuthentication
CookieTokenAuthentication = JWTAccessAuthentication
