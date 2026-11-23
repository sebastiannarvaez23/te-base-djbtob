"""Unit tests de la factory get_email_service."""

import pytest
from django.test import override_settings

from core.email import (
    FakeEmailService,
    FallbackEmailService,
    SmtpEmailService,
    get_email_service,
)
from core.email.infrastructure.resend import ResendEmailService
from core.errors import AppErrorCode, ServerException

pytestmark = pytest.mark.unit


class TestGetEmailService:

    @override_settings(EMAIL_PROVIDER='fake')
    def test_fake_provider(self):
        assert isinstance(get_email_service(), FakeEmailService)

    @override_settings(EMAIL_PROVIDER='smtp')
    def test_smtp_provider(self):
        assert isinstance(get_email_service(), SmtpEmailService)

    @override_settings(
        EMAIL_PROVIDER='resend',
        RESEND_API_KEY='re_test',
        EMAIL_SMTP_FALLBACK=True,
    )
    def test_resend_wraps_smtp_fallback(self):
        svc = get_email_service()
        assert isinstance(svc, FallbackEmailService)
        assert isinstance(svc.primary, ResendEmailService)
        assert isinstance(svc.fallback, SmtpEmailService)

    @override_settings(
        EMAIL_PROVIDER='resend',
        RESEND_API_KEY='re_test',
        EMAIL_SMTP_FALLBACK=False,
    )
    def test_resend_without_fallback_is_bare(self):
        assert isinstance(get_email_service(), ResendEmailService)

    def test_override_argument_wins_over_settings(self):
        with override_settings(EMAIL_PROVIDER='smtp'):
            assert isinstance(get_email_service('fake'), FakeEmailService)

    @override_settings(
        EMAIL_PROVIDER='resend',
        RESEND_API_KEY='',
        EMAIL_SMTP_FALLBACK=True,
    )
    def test_resend_without_key_falls_back_to_smtp(self):
        assert isinstance(get_email_service(), SmtpEmailService)

    @override_settings(
        EMAIL_PROVIDER='resend',
        RESEND_API_KEY='',
        EMAIL_SMTP_FALLBACK=False,
    )
    def test_resend_without_key_raises_when_fallback_off(self):
        with pytest.raises(ServerException) as exc:
            get_email_service()
        assert exc.value.code == AppErrorCode.EMAIL_PROVIDER_UNAVAILABLE

    @override_settings(EMAIL_PROVIDER='mailgun')
    def test_unknown_provider_raises(self):
        with pytest.raises(ServerException) as exc:
            get_email_service()
        assert exc.value.code == AppErrorCode.EMAIL_PROVIDER_UNAVAILABLE
