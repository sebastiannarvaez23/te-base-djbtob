import logging
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client.features.security.lifecycle.auth.application.email_confirmation import (
    ConfirmEmailUseCase, IssueEmailConfirmationTokenUseCase,
)
from client.features.security.lifecycle.auth.application.password_policy import (
    is_password_expired,
    rotate_password,
    start_password_clock,
)
from client.features.security.lifecycle.auth.application.password_recovery import (
    ConsumePasswordRecoveryTokenUseCase,
    IssuePasswordRecoveryTokenUseCase,
    ValidatePasswordRecoveryTokenUseCase,
)
from client.features.security.lifecycle.auth.application.throttle import (
    try_acquire_recovery_ip_slot,
    try_acquire_recovery_slot,
    try_acquire_resend_slot,
    try_acquire_two_factor_resend_slot,
)
from client.features.security.lifecycle.auth.application.two_factor import (
    FindTrustedDeviceUseCase,
    GetActiveTwoFactorChallengeUseCase,
    IssueTwoFactorChallengeUseCase,
    ListTrustedDevicesUseCase,
    OTP_TTL_MINUTES,
    PeekTwoFactorChallengeUseCase,
    RegisterTrustedDeviceUseCase,
    RevokeTrustedDeviceUseCase,
    RotateTwoFactorChallengeUseCase,
    StampTwoFactorRememberMeUseCase,
    TouchTrustedDeviceUseCase,
    VerifyTwoFactorChallengeUseCase,
    client_ip,
    generate_device_serial,
    hash_device,
    is_two_factor_enabled,
    parse_device_label,
    resolve_login_location,
)
from client.features.security.lifecycle.auth.application.use_cases import BuildSessionUseCase
from client.features.security.lifecycle.auth.infrastructure.composition import (
    issue_client_session_use_case,
    login_user_use_case,
    logout_client_session_use_case,
    session_policy,
)
from client.features.security.lifecycle.auth.infrastructure.refresh_token_store import (
    RedisClientRefreshStore,
)
from client.features.security.lifecycle.auth.infrastructure.repositories import (
    DjangoSessionRepository,
)
from client.features.security.lifecycle.auth.presentation.bodies import (
    ChangePasswordBody,
    ConfirmEmailBody,
    LoginBody,
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
    PasswordResetValidateBody,
    ResendConfirmationBody,
    ResendTwoFactorBody,
    VerifyTwoFactorBody,
)
from core.audit import audit_log, security_log
from core.errors import AppErrorCode, AuthException, EmailNotVerifiedException, NotFoundException
from core.validators import ValidationError, ValidationCode, validated_body
from core.auth.cookie_authentication import (
    JWTAccessAuthentication,
    RefreshTokenAuthentication,
)
from core.auth.cookies import (
    set_auth_cookies, clear_auth_cookies,
    read_device_serial, set_device_cookie, clear_device_cookie,
    ACCESS_CLIENT_COOKIE, REFRESH_CLIENT_COOKIE,
)
from core.auth.inactivity import carried_last_activity
from core.auth.jwt_service import create_access_token
from core.access.billing_recovery import resolve_access_mode_for_user
from core.auth import refresh_service
from core.decorators.response import wrap_response
from core.parameters import get_parameter
from client.features.security.identity.identity.domain.profile_picture import (
    resolve_profile_picture_url,
    user_picture_object_key,
)

logger = logging.getLogger('app.api')

_profile_storage_ready = False


def _ensure_profile_storage_once() -> None:
    global _profile_storage_ready
    if _profile_storage_ready:
        return
    try:
        from client.features.security.identity.identity.infrastructure.profile_storage import ensure_profile_storage
        ensure_profile_storage()
        _profile_storage_ready = True
    except Exception as exc:
        logger.warning('Could not ensure profile storage: %s', exc)


def _session_payload(user, session) -> dict:
    """Serialize session and guarantee a non-null sidebar avatar URL."""
    _ensure_profile_storage_once()
    payload = session.model_dump(mode='json')
    payload.setdefault('user', {})
    payload['user']['picture'] = resolve_profile_picture_url(user_picture_object_key(user))
    return payload


def _confirm_token_ttl_hours() -> int:
    return int(get_parameter('EMAIL_CFM_TTL_H', default=24))


def _recovery_token_ttl_minutes() -> int:
    return int(get_parameter('PWD_RESET_TTL_M', default=60))


def _issue_and_dispatch_confirmation(user) -> None:
    """Create a token and fire the EMAIL_CONFIRM message (best effort)."""
    from platform.features.communication.notification.dispatchers import (
        dispatch_email_confirm,
    )

    ttl_hours = _confirm_token_ttl_hours()
    raw = IssueEmailConfirmationTokenUseCase(ttl_hours=ttl_hours).execute(user)
    confirmation_url = f'{settings.EMAIL_CFM_URL}?token={raw}'
    dispatch_email_confirm(
        user=user, confirmation_url=confirmation_url, expiration_time=ttl_hours,
    )


def _issue_and_dispatch_recovery(user, request) -> None:
    """Create a recovery token and fire RESCUE_CREDENTIALS (best effort)."""
    from platform.features.communication.notification.dispatchers import (
        dispatch_rescue_credentials,
    )

    ttl_minutes = _recovery_token_ttl_minutes()
    raw = IssuePasswordRecoveryTokenUseCase(ttl_minutes=ttl_minutes).execute(
        user,
        request_ip=request.META.get('REMOTE_ADDR') or None,
        request_ua=request.META.get('HTTP_USER_AGENT', ''),
    )
    reset_password_url = f'{settings.PASSWORD_RESET_URL}?token={raw}'
    dispatch_rescue_credentials(
        user=user,
        reset_password_url=reset_password_url,
        expiration_time=ttl_minutes,
    )


def _dispatch_2fa_email(user, otp: str, request) -> None:
    """Fire 2FA_AUTH with the one-time code (best effort, never raises)."""
    from platform.features.communication.notification.dispatchers import (
        dispatch_2fa_auth,
    )

    ip = client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')
    dispatch_2fa_auth(
        user=user,
        otp_code=otp,
        login_ip=ip or 'Unknown',
        login_time=timezone.localtime().strftime('%Y-%m-%d %H:%M'),
        login_device=parse_device_label(ua),
        login_location=resolve_login_location(request),
        expiration_time=OTP_TTL_MINUTES,
    )


def _client_access_claims(request) -> tuple:
    """Read user_id / sid from the access cookie without enforcing expiry."""
    import jwt as pyjwt

    access = request.COOKIES.get(ACCESS_CLIENT_COOKIE)
    if not access:
        return None, None
    try:
        payload = pyjwt.decode(
            access, settings.SECRET_KEY, algorithms=['HS256'],
            options={'verify_exp': False},
        )
    except pyjwt.InvalidTokenError:
        return None, None
    if payload.get('user_type') != 'client':
        return None, None
    return payload.get('user_id'), payload.get('sid')


def _issue_client_session(
    request,
    user,
    *,
    access=None,
    remember_me: bool = False,
):
    """HTTP adapter: mint JWT/cookies around IssueClientSessionUseCase."""
    issued = issue_client_session_use_case().execute(
        user,
        access=access,
        current_refresh_raw=request.COOKIES.get(REFRESH_CLIENT_COOKIE) or None,
        schema_name=connection.schema_name,
        ip=client_ip(request) or '',
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        remember_me=bool(remember_me),
    )
    access_token = create_access_token(
        user_id=user.pk,
        user_type='client',
        schema_name=connection.schema_name,
        session_id=issued.session_id,
        access_mode=issued.session.access_mode,
        username=getattr(user, 'username', '') or '',
    )

    security_log(
        request,
        event_type='LOGIN_SUCCESS',
        target_user_id=user.pk,
        resource=request.path,
        detail=f'username={user.username}',
    )
    company_schema = getattr(getattr(user, 'company', None), 'schema_name', None)
    audit_log(
        request, 'User', user.pk, 'LOGIN', f'User {user.username} logged in',
        schema_name=company_schema,
    )

    response = wrap_response(_session_payload(user, issued.session))
    set_auth_cookies(
        response, access_token, issued.refresh_token,
        persistent=issued.remember_me,
    )
    return response


class UserLoginAPIView(APIView):
    """User login. Sets HttpOnly cookies with access + refresh tokens.

    The response body contains the full session payload — the frontend
    never sees raw token values in JavaScript.

    When ``DOUBLE_FA_AUTH`` is on and the device serial is unknown, the
    response is a 2FA challenge (no cookies) instead of a session.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(LoginBody)
    def post(self, request, *args, body: dict, **kwargs):

        remember_me = bool(body.get('remember_me'))

        try:
            auth_result = login_user_use_case().execute(
                body.get('username', ''),
                body.get('password', ''),
            )
        except EmailNotVerifiedException as exc:
            # Fire-and-forget: re-send the confirmation link (throttled) so
            # the user can act on the error message they're about to see.
            unverified_user_id = (exc.context or {}).get('user_id')
            if unverified_user_id and try_acquire_resend_slot(unverified_user_id):
                try:
                    User = get_user_model()
                    unverified_user = User.objects.filter(pk=unverified_user_id).first()
                    if unverified_user is not None:
                        _issue_and_dispatch_confirmation(unverified_user)
                except Exception:
                    logger.exception('Auto-resend on unverified login failed')
            raise

        user = auth_result.user
        start_password_clock(user)
        if is_password_expired(user):
            security_log(
                request,
                event_type='PASSWORD_EXPIRED',
                target_user_id=user.pk,
                resource='/api/v1/auth/login/',
                detail=f'username={user.username}',
            )
            raise AuthException(AppErrorCode.AUTH_PASSWORD_EXPIRED)

        session_policy().ensure_can_open_session(
            user.pk,
            current_refresh_raw=request.COOKIES.get(REFRESH_CLIENT_COOKIE) or None,
        )

        device_id = read_device_serial(request)
        if is_two_factor_enabled():
            trusted = FindTrustedDeviceUseCase().execute(user, device_id)
            if trusted is None:
                active = GetActiveTwoFactorChallengeUseCase().execute(user)
                # Reuse only while the resend window is closed. A failed first
                # send still leaves a live challenge (dispatch is fire-and-forget),
                # so a login retry must mint a new OTP, expire the previous one,
                # and mail it again.
                if active is not None and not try_acquire_two_factor_resend_slot(user.pk):
                    StampTwoFactorRememberMeUseCase().execute(
                        active.challenge_id, remember_me,
                    )
                    return wrap_response(active.model_dump(mode='json'))
                otp, challenge = IssueTwoFactorChallengeUseCase().execute(
                    user,
                    ip=client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    remember_me=remember_me,
                )
                _dispatch_2fa_email(user, otp, request)
                security_log(
                    request,
                    event_type='TWO_FA_CHALLENGE_ISSUED',
                    target_user_id=user.pk,
                    resource='/api/v1/auth/login/',
                    detail=f'username={user.username}',
                )
                return wrap_response(challenge.model_dump(mode='json'))
            TouchTrustedDeviceUseCase().execute(
                trusted,
                ip=client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

        return _issue_client_session(
            request, user, access=auth_result.access, remember_me=remember_me,
        )


class VerifyTwoFactorAPIView(APIView):
    """Consume a 2FA challenge and complete login on the presented device."""

    authentication_classes = []
    permission_classes = []

    @validated_body(VerifyTwoFactorBody)
    def post(self, request, *args, body: dict, **kwargs):

        try:
            verified = VerifyTwoFactorChallengeUseCase().execute(
                body['challenge_id'],
                body['otp_code'],
                ip=client_ip(request),
            )
        except Exception:
            security_log(
                request,
                event_type='TWO_FA_FAILED',
                resource='/api/v1/auth/login/verify-2fa/',
                detail='invalid_or_expired_challenge',
            )
            raise

        user = verified.user
        remember = bool(body.get('remember_device'))
        serial = None
        if remember:
            serial = generate_device_serial()
            try:
                RegisterTrustedDeviceUseCase().execute(
                    user,
                    serial,
                    ip=client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            except Exception:
                logger.exception('Could not persist trusted device after 2FA')
                serial = None

        security_log(
            request,
            event_type='TWO_FA_VERIFIED',
            target_user_id=user.pk,
            resource='/api/v1/auth/login/verify-2fa/',
            detail=f'username={user.username}',
        )
        response = _issue_client_session(
            request, user, remember_me=verified.remember_me,
        )
        if serial:
            set_device_cookie(response, serial)
        return response


class ResendTwoFactorAPIView(APIView):
    """Re-send the 2FA email for a live challenge.

    Throttled per user. Always returns the public challenge payload when
    the challenge is still valid, including when the send is throttled,
    so the UI can keep the same session without leaking throttle state.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ResendTwoFactorBody)
    def post(self, request, *args, body: dict, **kwargs):

        challenge_id = body['challenge_id']
        user, challenge = PeekTwoFactorChallengeUseCase().execute(challenge_id)

        if try_acquire_two_factor_resend_slot(user.pk):
            user, otp, challenge = RotateTwoFactorChallengeUseCase().execute(challenge_id)
            _dispatch_2fa_email(user, otp, request)
            security_log(
                request,
                event_type='TWO_FA_RESENT',
                target_user_id=user.pk,
                resource='/api/v1/auth/login/resend-2fa/',
                detail=f'username={user.username}',
            )

        return wrap_response(challenge.model_dump(mode='json'))


class TrustedDeviceListAPIView(APIView):
    """List the caller's active trusted devices."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = ListTrustedDevicesUseCase().execute(
            request.user,
            read_device_serial(request),
        )
        return wrap_response([item.model_dump(mode='json') for item in devices])


class TrustedDeviceRevokeAPIView(APIView):
    """Revoke one trusted device belonging to the caller."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id):
        try:
            parsed_id = uuid.UUID(str(device_id))
        except (ValueError, TypeError, AttributeError):
            raise NotFoundException(AppErrorCode.AUTH_DEVICE_NOT_FOUND)

        revoked_hash = RevokeTrustedDeviceUseCase().execute(request.user, parsed_id)
        security_log(
            request,
            event_type='TRUSTED_DEVICE_REVOKED',
            target_user_id=request.user.pk,
            resource=request.path,
            detail=f'device_id={parsed_id}',
        )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        serial = read_device_serial(request)
        if serial and hash_device(request.user.pk, serial) == revoked_hash:
            clear_device_cookie(response)
        return response


class UserMeAPIView(APIView):
    """Rebuild the session payload for the authenticated user (cookie-based)."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = BuildSessionUseCase(DjangoSessionRepository()).execute(request.user)
        return wrap_response(_session_payload(request.user, session))


class UserActivityAPIView(APIView):
    """Record that the signed-in company user is still at the keyboard.

    Authentication already slides ``last_activity_at`` (throttled). This
    endpoint exists so the client can report activity without a business
    call. A silent token refresh must not hit it: refresh is not activity.
    """

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserRefreshAPIView(APIView):
    """Rotate both access and refresh tokens using the refresh cookie."""

    authentication_classes = [RefreshTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if response.status_code == 401:
            clear_auth_cookies(response)
        return response

    def post(self, request):
        # Revoke the old refresh token (rotation)
        old_raw = request._refresh_token_raw
        old_record = request._refresh_record
        refresh_service.revoke(old_raw, user_type='client')

        remember_me = refresh_service.record_is_remembered(old_record)
        schema_name = old_record.get('schema_name', connection.schema_name)
        raw_refresh = refresh_service.generate_raw_token()
        _, token_id = refresh_service.store(
            raw_token=raw_refresh,
            user_id=request.user.pk,
            user_type='client',
            schema_name=schema_name,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ttl_seconds=refresh_service.refresh_ttl_seconds(remember_me=remember_me),
            remember_me=remember_me,
            # A silent refresh is not user activity. Keep the idle clock.
            last_activity_at=carried_last_activity(old_record),
        )
        access_token = create_access_token(
            user_id=request.user.pk,
            user_type='client',
            schema_name=schema_name,
            session_id=token_id,
            access_mode=resolve_access_mode_for_user(request.user),
            username=getattr(request.user, 'username', '') or '',
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, access_token, raw_refresh, persistent=remember_me)
        return response


class UserLogoutAPIView(APIView):
    """Clear client auth cookies and revoke refresh tokens from Redis.

    With ``MULTI_SESSIONS`` off, every client session for the user is
    dropped. With it on, only this browser's token is revoked.

    No authentication required — logout must always succeed regardless
    of token state.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        access_user_id, access_session_id = _client_access_claims(request)
        logout_client_session_use_case().execute(
            current_refresh_raw=request.COOKIES.get(REFRESH_CLIENT_COOKIE) or None,
            access_user_id=access_user_id,
            access_session_id=access_session_id,
        )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class ConfirmEmailAPIView(APIView):
    """Consume an email-confirmation token and flip ``email_verified_at``.

    Public endpoint — the raw token is the only thing required.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ConfirmEmailBody)
    def post(self, request, *args, body: dict, **kwargs):

        user = ConfirmEmailUseCase().execute(body['token'])

        security_log(
            request,
            event_type='EMAIL_CONFIRMED',
            target_user_id=user.pk,
            resource='/api/v1/auth/confirm-email/',
            detail=f'username={user.username}',
        )
        audit_log(
            request, 'User', user.pk, 'EMAIL_CONFIRMED',
            f'User {user.username} confirmed email',
            schema_name=getattr(getattr(user, 'company', None), 'schema_name', None),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResendConfirmationAPIView(APIView):
    """Re-issue and re-send a confirmation email.

    Always returns 204 regardless of lookup or throttle result to avoid
    account enumeration. The throttle is enforced atomically on the
    Redis side before anything is written to the database.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ResendConfirmationBody)
    def post(self, request, *args, body: dict, **kwargs):

        email = (body.get('email') or '').strip()
        username = (body.get('username') or '').strip()
        if not email and not username:
            return ResendConfirmationBody.error_response([
                ValidationError(
                    field='email',
                    code=ValidationCode.REQUIRED,
                    detail='Either email or username is required.',
                ),
            ])

        User = get_user_model()
        user = None
        try:
            if email:
                user = User.objects.filter(email__iexact=email).first()
            if user is None and username:
                user = User.objects.filter(username=username).first()
        except Exception:
            logger.exception('ResendConfirmation: user lookup failed')

        if user is not None and user.email_verified_at is None and user.is_active:
            if try_acquire_resend_slot(user.pk):
                try:
                    _issue_and_dispatch_confirmation(user)
                    security_log(
                        request,
                        event_type='EMAIL_CONFIRM_RESENT',
                        target_user_id=user.pk,
                        resource='/api/v1/auth/resend-confirmation/',
                        detail=f'username={user.username}',
                    )
                except Exception:
                    logger.exception('ResendConfirmation: issue/dispatch failed')

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestAPIView(APIView):
    """Request a password-reset link.

    Always responds 204 to prevent account-enumeration: the caller cannot
    distinguish "email exists" from "email does not". Throttled per user
    and per IP via Redis SETNX. The token itself is issued in
    ``_issue_and_dispatch_recovery`` and emailed with the RESCUE_CREDENTIALS
    template.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(PasswordResetRequestBody)
    def post(self, request, *args, body: dict, **kwargs):

        ip = request.META.get('REMOTE_ADDR', '')
        if not try_acquire_recovery_ip_slot(ip):
            # Silent throttle — same 204 to keep the response shape uniform.
            return Response(status=status.HTTP_204_NO_CONTENT)

        email = (body.get('email') or '').strip()
        User = get_user_model()
        user = None
        try:
            user = User.objects.filter(email__iexact=email).first()
        except Exception:
            logger.exception('PasswordResetRequest: user lookup failed')

        if user is not None and user.is_active:
            if try_acquire_recovery_slot(user.pk):
                try:
                    _issue_and_dispatch_recovery(user, request)
                    security_log(
                        request,
                        event_type='PWD_RESET_REQUESTED',
                        target_user_id=user.pk,
                        resource='/api/v1/auth/password-reset/request/',
                        detail=f'username={user.username}',
                    )
                except Exception:
                    logger.exception('PasswordResetRequest: issue/dispatch failed')

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetValidateAPIView(APIView):
    """Check whether a recovery token can still be consumed.

    Lets the SPA decide whether to render the new-password form or a
    "link expired" screen without actually burning the token. Returns
    204 on success; AuthException → AUTH_004 on failure.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(PasswordResetValidateBody)
    def post(self, request, *args, body: dict, **kwargs):

        ValidatePasswordRecoveryTokenUseCase().execute(body['token'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordAPIView(APIView):
    """Rotate a password using the current one (expired-password login path).

    Re-validates credentials so this stays public without a session.
    Does not issue cookies — the client must sign in with the new password.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ChangePasswordBody)
    def post(self, request, *args, body: dict, **kwargs):

        auth_result = login_user_use_case().execute(
            body['username'],
            body['current_password'],
        )
        user = auth_result.user
        rotate_password(user, body['new_password'])
        security_log(
            request,
            event_type='PASSWORD_CHANGED',
            target_user_id=user.pk,
            resource='/api/v1/auth/password/change/',
            detail=f'username={user.username}',
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmAPIView(APIView):
    """Consume a recovery token and rotate the user's password.

    Revokes every active client refresh-token for the user so any
    parallel session held by the attacker is invalidated.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(PasswordResetConfirmBody)
    def post(self, request, *args, body: dict, **kwargs):

        try:
            user = ConsumePasswordRecoveryTokenUseCase().execute(
                raw_token=body['token'],
                new_password=body['password'],
            )
        except Exception:
            security_log(
                request,
                event_type='PWD_RESET_FAILED',
                resource='/api/v1/auth/password-reset/confirm/',
                detail='invalid_or_expired_token',
            )
            raise

        try:
            RedisClientRefreshStore().revoke_all_for_user(user.pk)
        except Exception:
            logger.exception('PasswordResetConfirm: refresh revocation failed')

        security_log(
            request,
            event_type='PWD_RESET_COMPLETED',
            target_user_id=user.pk,
            resource='/api/v1/auth/password-reset/confirm/',
            detail=f'username={user.username}',
        )
        audit_log(
            request, 'User', user.pk, 'PASSWORD_RESET',
            f'User {user.username} reset password via recovery link',
            schema_name=getattr(getattr(user, 'company', None), 'schema_name', None),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
