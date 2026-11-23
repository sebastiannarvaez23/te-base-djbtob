"""
Notification dispatchers — one function per email template.

Each dispatcher:
  1. Receives domain objects (User, Company, Subscription…)
  2. Builds the typed context schema
  3. Delegates to NotificationService.send_email()

This keeps template-specific knowledge isolated here and out of
the calling code (views, use cases, etc.).
"""

import logging
import threading
from datetime import datetime

from django.conf import settings

from .contexts import (
    CompanyDeregistrationContext,
    EmailConfirmContext,
    OnboardingResumeContext,
    RescueCredentialsContext,
    TwoFactorAuthContext,
    WelcomeAdminContext,
    WelcomeUserContext,
)
from .service import NotificationService

logger = logging.getLogger('app.api')

PLATFORM_URL = 'https://base.local/dashboard'
SUPPORT_EMAIL = 'soporte@base.local'

_MONTHS_ES = (
    '',
    'enero',
    'febrero',
    'marzo',
    'abril',
    'mayo',
    'junio',
    'julio',
    'agosto',
    'septiembre',
    'octubre',
    'noviembre',
    'diciembre',
)


def _support_email() -> str:
    return getattr(settings, 'PLATFORM_SUPPORT_EMAIL', None) or SUPPORT_EMAIL


def _display_name(user) -> str:
    return (
        f'{getattr(user, "first_name", None) or ""} '
        f'{getattr(user, "last_name", None) or ""}'
    ).strip() or getattr(user, 'username', '') or getattr(user, 'email', '')


def format_company_document(nit: str) -> str:
    """Colombian NIT display: 9001234567 → 900.123.456-7."""
    digits = ''.join(ch for ch in (nit or '') if ch.isdigit())
    if len(digits) < 2:
        return nit or ''
    body, check = digits[:-1], digits[-1]
    groups: list[str] = []
    while body:
        groups.append(body[-3:])
        body = body[:-3]
    return f'{ ".".join(reversed(groups)) }-{check}'


def format_deactivation_date(value) -> str:
    """Spanish calendar datetime, e.g. '15 de septiembre de 2026, 10:42 a. m.'."""
    from django.utils import timezone as dj_tz

    if value is None:
        dt = dj_tz.now()
    elif isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt)
    local = dj_tz.localtime(dt)
    hour12 = local.hour % 12 or 12
    period = 'a. m.' if local.hour < 12 else 'p. m.'
    return (
        f'{local.day} de {_MONTHS_ES[local.month]} de {local.year}, '
        f'{hour12}:{local.minute:02d} {period}'
    )


def dispatch_welcome_admin(*, user, company, subscription, company_subscription) -> None:
    """
    Send the WELCOME_ADMIN email after a new company + admin user is registered.

    Runs in a background thread so it never blocks the HTTP response.
    """
    modules_qs = subscription.subscription_modules.all()
    modules_list = '\n'.join(f'- {m.module_code}' for m in modules_qs) or '- Acceso básico a la plataforma'

    context = WelcomeAdminContext(
        user_name=f'{user.first_name} {user.last_name}',
        user_email=user.email,
        username=user.username,
        company_name=company.name,
        subscription_name=subscription.name,
        subscription_code=subscription.code,
        price=float(subscription.price),
        start_date=company_subscription.start_date.strftime('%Y-%m-%d'),
        end_date=company_subscription.end_date.strftime('%Y-%m-%d'),
        modules_list=modules_list,
        platform_url=PLATFORM_URL,
        support_email=SUPPORT_EMAIL,
        current_year=datetime.now().year,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='WELCOME_ADMIN',
                to=[user.email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error(f'dispatch_welcome_admin failed for user={user.email}: {exc}')

    threading.Thread(target=_send, daemon=True).start()


def dispatch_welcome_user(*, user, company) -> None:
    """Send WELCOME_USER after an admin creates a company collaborator.

    Issues a password-recovery token so the invitee can activate their account
    and choose a password. Runs in a background thread.
    """
    from core.parameters import get_parameter
    from client.features.security.lifecycle.auth.application.password_recovery import (
        IssuePasswordRecoveryTokenUseCase,
    )

    ttl_minutes = int(get_parameter('USER_ACTIVATION_TTL_M', default=45))
    raw = IssuePasswordRecoveryTokenUseCase(ttl_minutes=ttl_minutes).execute(user)
    activation_url = f'{settings.USER_ACTIVATION_URL}?token={raw}'
    support = getattr(settings, 'PLATFORM_SUPPORT_EMAIL', None) or SUPPORT_EMAIL

    context = WelcomeUserContext(
        user_name=f'{user.first_name or ""} {user.last_name or ""}'.strip() or user.username,
        user_email=user.email,
        company_name=company.name,
        current_year=datetime.now().year,
        support_email=support,
        activation_url=activation_url,
        expiration_time=ttl_minutes,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='WELCOME_USER',
                to=[user.email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error('dispatch_welcome_user failed for user=%s: %s', user.email, exc)

    threading.Thread(target=_send, daemon=True).start()


def dispatch_email_confirm(*, user, confirmation_url: str, expiration_time: int) -> None:
    """Send the EMAIL_CONFIRM message with the single-use confirmation link.

    Runs in a background thread; never raises into the caller.
    """
    context = EmailConfirmContext(
        user_name=f'{user.first_name or ""} {user.last_name or ""}'.strip() or user.username,
        confirmation_url=confirmation_url,
        expiration_time=expiration_time,
        support_email=SUPPORT_EMAIL,
        current_year=datetime.now().year,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='EMAIL_CONFIRM',
                to=[user.email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error(f'dispatch_email_confirm failed for user={user.email}: {exc}')

    threading.Thread(target=_send, daemon=True).start()


def dispatch_rescue_credentials(*, user, reset_password_url: str, expiration_time: int) -> None:
    """Send the RESCUE_CREDENTIALS message with the password-reset link.

    ``expiration_time`` is expressed in minutes (the reset window is
    intentionally short — see PWD_RESET_TTL_M).

    Runs in a background thread; never raises into the caller.
    """
    context = RescueCredentialsContext(
        user_name=f'{user.first_name or ""} {user.last_name or ""}'.strip() or user.username,
        user_email=user.email,
        reset_password_url=reset_password_url,
        expiration_time=expiration_time,
        support_email=SUPPORT_EMAIL,
        current_year=datetime.now().year,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='RESCUE_CREDENTIALS',
                to=[user.email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error(f'dispatch_rescue_credentials failed for user={user.email}: {exc}')

    threading.Thread(target=_send, daemon=True).start()


def dispatch_onboarding_resume(*, to_email: str, resume_url: str, expires_in_days: int) -> None:
    """Send the ONBOARDING_RESUME magic-link so the user can continue registration.

    Runs in a background thread; never raises into the caller.
    """
    context = OnboardingResumeContext(
        resume_url=resume_url,
        expires_in_days=expires_in_days,
        support_email=SUPPORT_EMAIL,
        current_year=datetime.now().year,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='ONBOARDING_RESUME',
                to=[to_email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error(f'dispatch_onboarding_resume failed for email={to_email}: {exc}')

    threading.Thread(target=_send, daemon=True).start()


def dispatch_2fa_auth(
    *,
    user,
    otp_code: str,
    login_ip: str,
    login_time: str,
    login_device: str,
    login_location: str,
    expiration_time: int,
) -> None:
    """Send the 2FA_AUTH message with the one-time login code.

    Runs in a background thread; never raises into the caller. The OTP is
    included in the template context only — it is not logged here.
    """
    support = getattr(settings, 'PLATFORM_SUPPORT_EMAIL', None) or SUPPORT_EMAIL
    context = TwoFactorAuthContext(
        login_ip=login_ip or 'Unknown',
        otp_code=otp_code,
        user_name=(
            f'{user.first_name or ""} {user.last_name or ""}'.strip()
            or user.username
        ),
        login_time=login_time,
        current_year=datetime.now().year,
        login_device=login_device or 'Unknown',
        support_email=support,
        login_location=login_location or 'Unknown location',
        expiration_time=expiration_time,
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='2FA_AUTH',
                to=[user.email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error('dispatch_2fa_auth failed for user=%s: %s', user.email, exc)

    threading.Thread(target=_send, daemon=True).start()


def dispatch_company_deregistration(
    *,
    user,
    company_name: str,
    company_nit: str,
    closed_at,
    reason: str,
) -> None:
    """Send COMPANY_DEREGISTRATION to the company administrator after close.

    Runs in a background thread; never raises into the caller.
    """
    to_email = getattr(user, 'email', None)
    if not to_email:
        logger.warning('dispatch_company_deregistration skipped: missing administrator email')
        return

    context = CompanyDeregistrationContext(
        user_name=_display_name(user),
        company_name=company_name,
        current_year=datetime.now().year,
        support_email=_support_email(),
        company_document=format_company_document(company_nit),
        deactivation_date=format_deactivation_date(closed_at),
        deactivation_reason=(reason or '').strip(),
    )

    def _send():
        try:
            NotificationService().send_email(
                template_code='COMPANY_DEREGISTRATION',
                to=[to_email],
                context=context.model_dump(),
            )
        except Exception as exc:
            logger.error(
                'dispatch_company_deregistration failed for user=%s: %s',
                to_email,
                exc,
            )

    threading.Thread(target=_send, daemon=True).start()
