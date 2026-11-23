from django.conf import settings
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import security_log
from core.auth.cookie_authentication import (
    JWTAdminAccessAuthentication,
    AdminRefreshTokenAuthentication,
)
from core.auth.cookies import (
    REFRESH_ADMIN_COOKIE,
    ACCESS_ADMIN_COOKIE,
    read_device_serial,
    set_auth_cookies,
    clear_auth_cookies,
    set_device_cookie,
)
from core.auth.inactivity import carried_last_activity
from core.auth.jwt_service import create_access_token
from core.auth import refresh_service
from core.auth.login_context import parse_device_label, resolve_login_location
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, AuthException
from core.validators import validated_body
from django.utils import timezone

from platform.features.security.auth.auth.application.password_policy import (
    is_password_expired,
    rotate_password,
)
from platform.features.security.auth.auth.application.two_factor import (
    OTP_TTL_MINUTES,
    generate_device_serial,
    is_two_factor_enabled,
)
from platform.features.security.auth.auth.application.use_cases import (
    AdminLoginUseCase,
    BuildAdminSessionUseCase,
)
from platform.features.security.auth.auth.infrastructure.composition import (
    admin_login_lockout,
    admin_session_policy,
    find_admin_trusted_device,
    get_active_admin_two_factor_challenge,
    issue_admin_session,
    issue_admin_two_factor_challenge,
    logout_admin_session,
    peek_admin_two_factor_challenge,
    register_admin_trusted_device,
    rotate_admin_two_factor_challenge,
    touch_admin_trusted_device,
    verify_admin_two_factor_challenge,
)
from platform.features.security.auth.auth.infrastructure.repositories import (
    DjangoAdminAuthRepository,
    DjangoAdminSessionRepository,
)
from platform.features.security.auth.auth.presentation.bodies import (
    AdminChangePasswordBody,
    AdminLoginBody,
    AdminResendTwoFactorBody,
    AdminVerifyTwoFactorBody,
)

logger = logging.getLogger('app.api')

_profile_storage_ready = False


def _ensure_profile_storage_once() -> None:
    global _profile_storage_ready
    if _profile_storage_ready:
        return
    try:
        from platform.features.security.identity.identity.infrastructure.profile_storage import (
            ensure_profile_storage,
        )
        ensure_profile_storage()
        _profile_storage_ready = True
    except Exception as exc:
        logger.warning('Could not ensure admin profile storage: %s', exc)


def _client_ip(request) -> str:
    return request.META.get('REMOTE_ADDR', '') or ''


def _try_acquire_two_factor_resend_slot(user_id) -> bool:
    from django.core.cache import caches
    key = f'admin_two_factor_resend_throttle:{user_id}'
    return bool(caches['auth'].add(key, '1', timeout=30))


def _dispatch_2fa_email(user, otp: str, request) -> None:
    from platform.features.communication.notification.dispatchers import dispatch_2fa_auth

    dispatch_2fa_auth(
        user=user,
        otp_code=otp,
        login_ip=_client_ip(request) or 'Unknown',
        login_time=timezone.localtime().strftime('%Y-%m-%d %H:%M'),
        login_device=parse_device_label(request.META.get('HTTP_USER_AGENT', '')),
        login_location=resolve_login_location(request),
        expiration_time=OTP_TTL_MINUTES,
    )


def _admin_session_payload(user_orm):
    _ensure_profile_storage_once()
    from platform.features.security.identity.identity.application.use_cases import (
        GetAdminUserPreferencesUseCase,
    )
    from platform.features.security.identity.identity.domain.profile_picture import (
        resolve_profile_picture_url,
        user_picture_object_key,
    )
    from platform.features.security.identity.identity.infrastructure.repositories import (
        DjangoAdminUserPreferencesRepository,
    )

    role = user_orm.role
    preferences = GetAdminUserPreferencesUseCase(
        DjangoAdminUserPreferencesRepository(),
    ).execute(user_orm.id)
    session = BuildAdminSessionUseCase(DjangoAdminSessionRepository()).execute(user_orm)
    # Session contract (menu / features / inactivity) comes from Pydantic;
    # user blob stays assembled here until a dedicated AdminUserSchema lands.
    return {
        'user': {
            'id': str(user_orm.id),
            'username': user_orm.username,
            'email': user_orm.email,
            'first_name': user_orm.first_name,
            'last_name': user_orm.last_name,
            'telephone': user_orm.telephone or '',
            'picture': resolve_profile_picture_url(user_picture_object_key(user_orm)),
            'preferences': preferences.model_dump(mode='json'),
            'rol': {
                'id': str(role.id),
                'name': role.name,
                'description': role.description,
                'is_active': role.is_active,
                'created_at': (
                    role.created_at.isoformat().replace('+00:00', 'Z')
                    if role.created_at else None
                ),
                'updated_at': (
                    role.updated_at.isoformat().replace('+00:00', 'Z')
                    if role.updated_at else None
                ),
            },
            'is_active': user_orm.is_active,
            'is_superuser': user_orm.is_superuser,
            'last_login': (
                user_orm.last_login.isoformat().replace('+00:00', 'Z')
                if user_orm.last_login else None
            ),
            'created_at': user_orm.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': user_orm.updated_at.isoformat().replace('+00:00', 'Z'),
        },
        **session.model_dump(mode='json'),
    }


def _respond_with_admin_session(request, user, *, last_activity_at: str | None = None):
    issued = issue_admin_session().execute(
        user,
        current_refresh_raw=request.COOKIES.get(REFRESH_ADMIN_COOKIE) or None,
        ip=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        last_activity_at=last_activity_at,
    )
    security_log(
        request,
        event_type='ADMIN_LOGIN_SUCCESS',
        target_user_id=user.pk,
        resource='/api/v1/platform/auth/login/',
        detail=f'admin_username={user.username}',
    )
    response = wrap_response(_admin_session_payload(issued.user))
    set_auth_cookies(response, issued.access_token, issued.refresh_token, admin=True)
    return response


class AdminLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(AdminLoginBody)
    def post(self, request, *, body: dict):
        username = body['username']
        password = body['password']
        lockout = admin_login_lockout()
        lockout.assert_not_locked(username)

        use_case = AdminLoginUseCase(DjangoAdminAuthRepository())
        user = use_case.execute(username=username, password=password)
        if user is None:
            lockout.register_failure(username)
            security_log(
                request,
                event_type='ADMIN_LOGIN_FAILED',
                resource='/api/v1/platform/auth/login/',
                detail=f'attempted_username={username}',
            )
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        lockout.clear_failures(username)
        if is_password_expired(user):
            security_log(
                request,
                event_type='PASSWORD_EXPIRED',
                target_user_id=user.pk,
                resource='/api/v1/platform/auth/login/',
                detail=f'admin_username={user.username}',
            )
            raise AuthException(AppErrorCode.AUTH_PASSWORD_EXPIRED)

        admin_session_policy().ensure_can_open_session(
            user.pk,
            current_refresh_raw=request.COOKIES.get(REFRESH_ADMIN_COOKIE) or None,
        )

        device_id = read_device_serial(request, admin=True)
        if is_two_factor_enabled():
            trusted = find_admin_trusted_device().execute(user, device_id)
            if trusted is None:
                active = get_active_admin_two_factor_challenge().execute(user)
                if active is not None and not _try_acquire_two_factor_resend_slot(user.pk):
                    return wrap_response(active.model_dump(mode='json'))
                otp, challenge = issue_admin_two_factor_challenge().execute(
                    user,
                    ip=_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
                _dispatch_2fa_email(user, otp, request)
                security_log(
                    request,
                    event_type='TWO_FA_CHALLENGE_ISSUED',
                    target_user_id=user.pk,
                    resource='/api/v1/platform/auth/login/',
                    detail=f'admin_username={user.username}',
                )
                return wrap_response(challenge.model_dump(mode='json'))
            touch_admin_trusted_device().execute(
                trusted,
                ip=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

        return _respond_with_admin_session(request, user)


class AdminVerifyTwoFactorAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(AdminVerifyTwoFactorBody)
    def post(self, request, *, body: dict):
        try:
            verified = verify_admin_two_factor_challenge().execute(
                body['challenge_id'],
                body['otp_code'],
                ip=_client_ip(request),
            )
        except Exception:
            security_log(
                request,
                event_type='TWO_FA_FAILED',
                resource='/api/v1/platform/auth/login/verify-2fa/',
                detail='invalid_or_expired_challenge',
            )
            raise

        user = verified.user
        serial = None
        if body.get('remember_device'):
            serial = generate_device_serial()
            try:
                register_admin_trusted_device().execute(
                    user,
                    serial,
                    ip=_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            except Exception:
                logger.exception('Could not persist admin trusted device after 2FA')
                serial = None

        security_log(
            request,
            event_type='TWO_FA_VERIFIED',
            target_user_id=user.pk,
            resource='/api/v1/platform/auth/login/verify-2fa/',
            detail=f'admin_username={user.username}',
        )
        response = _respond_with_admin_session(request, user)
        if serial:
            set_device_cookie(response, serial, admin=True)
        return response


class AdminResendTwoFactorAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(AdminResendTwoFactorBody)
    def post(self, request, *, body: dict):
        challenge_id = body['challenge_id']
        user, challenge = peek_admin_two_factor_challenge().execute(challenge_id)
        if _try_acquire_two_factor_resend_slot(user.pk):
            user, otp, challenge = rotate_admin_two_factor_challenge().execute(
                challenge_id,
            )
            _dispatch_2fa_email(user, otp, request)
            security_log(
                request,
                event_type='TWO_FA_RESENT',
                target_user_id=user.pk,
                resource='/api/v1/platform/auth/login/resend-2fa/',
                detail=f'admin_username={user.username}',
            )
        return wrap_response(challenge.model_dump(mode='json'))


class AdminChangePasswordAPIView(APIView):
    """Rotate an expired admin password using the current one (public)."""

    authentication_classes = []
    permission_classes = []

    @validated_body(AdminChangePasswordBody)
    def post(self, request, *, body: dict):
        username = body['username']
        lockout = admin_login_lockout()
        lockout.assert_not_locked(username)

        use_case = AdminLoginUseCase(DjangoAdminAuthRepository())
        user = use_case.execute(
            username=username,
            password=body['current_password'],
        )
        if user is None:
            lockout.register_failure(username)
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        lockout.clear_failures(username)
        rotate_password(user, body['new_password'])
        try:
            refresh_service.revoke_all_for_user(user.pk, user_type='admin')
        except Exception:
            logger.exception('Admin password change: refresh revocation failed')
        security_log(
            request,
            event_type='PASSWORD_CHANGED',
            target_user_id=user.pk,
            resource='/api/v1/platform/auth/password/change/',
            detail=f'admin_username={user.username}',
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminMeAPIView(APIView):
    """Return the current admin session payload based on the JWT access cookie."""

    authentication_classes = [JWTAdminAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return wrap_response(_admin_session_payload(request.user))


class AdminActivityAPIView(APIView):
    """Record that the signed-in platform admin is still at the keyboard.

    Authentication already slides ``last_activity_at`` (throttled). This
    endpoint exists so the admin SPA can report activity without a business
    call. A silent token refresh must not hit it: refresh is not activity.
    """

    authentication_classes = [JWTAdminAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRefreshAPIView(APIView):
    """Rotate both access and refresh tokens using the refresh cookie."""

    authentication_classes = [AdminRefreshTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if response.status_code == 401:
            clear_auth_cookies(response, admin=True)
        return response

    def post(self, request):
        old_raw = request._refresh_token_raw
        old_record = getattr(request, '_refresh_record', None)
        refresh_service.revoke(old_raw, user_type='admin')

        raw_refresh = refresh_service.generate_raw_token()
        _, token_id = refresh_service.store(
            raw_token=raw_refresh,
            user_id=request.user.pk,
            user_type='admin',
            schema_name='public',
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            last_activity_at=carried_last_activity(old_record),
        )
        access_token = create_access_token(
            user_id=request.user.pk,
            user_type='admin',
            schema_name='public',
            session_id=token_id,
            username=getattr(request.user, 'username', '') or '',
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, access_token, raw_refresh, admin=True)
        return response


class AdminLogoutAPIView(APIView):
    """Clear admin auth cookies and revoke refresh tokens from Redis."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            access_user_id, access_session_id = self._resolve_access_identity(request)
            logout_admin_session().execute(
                current_refresh_raw=request.COOKIES.get(REFRESH_ADMIN_COOKIE) or None,
                access_user_id=access_user_id,
                access_session_id=access_session_id,
            )
        except Exception:
            pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response, admin=True)
        return response

    @staticmethod
    def _resolve_access_identity(request):
        import jwt as pyjwt

        access = request.COOKIES.get(ACCESS_ADMIN_COOKIE)
        if not access:
            return None, None
        try:
            payload = pyjwt.decode(
                access, settings.SECRET_KEY, algorithms=['HS256'],
                options={'verify_exp': False},
            )
            if payload.get('user_type') == 'admin':
                return payload.get('user_id'), payload.get('sid') or None
        except pyjwt.InvalidTokenError:
            pass
        return None, None
