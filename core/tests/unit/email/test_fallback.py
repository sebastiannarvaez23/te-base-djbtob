"""Unit tests del respaldo Resend → SMTP."""

from unittest.mock import MagicMock

import pytest

from core.email import FakeEmailService, FallbackEmailService
from core.email.domain.schemas import EmailAttachment
from core.tests.unit.email.helpers import email_message

pytestmark = pytest.mark.unit


class TestFallbackEmailService:

    def test_uses_primary_when_it_succeeds(self):
        primary = FakeEmailService()
        fallback = FakeEmailService()
        svc = FallbackEmailService(primary, fallback)

        ok = svc.send(email_message())

        assert ok is True
        assert len(primary.sent) == 1
        assert fallback.sent == []

    def test_uses_smtp_when_primary_returns_false(self):
        primary = MagicMock()
        primary.provider = 'resend'
        primary.send.return_value = False
        fallback = FakeEmailService()
        svc = FallbackEmailService(primary, fallback)

        ok = svc.send(email_message())

        assert ok is True
        primary.send.assert_called_once()
        assert len(fallback.sent) == 1
        assert fallback.sent[0].subject == 'Hi'

    def test_uses_smtp_when_primary_raises(self):
        primary = MagicMock()
        primary.provider = 'resend'
        primary.send.side_effect = RuntimeError('domain not verified')
        fallback = FakeEmailService()
        svc = FallbackEmailService(primary, fallback)

        ok = svc.send(email_message())

        assert ok is True
        assert len(fallback.sent) == 1

    def test_returns_false_when_both_fail(self):
        primary = MagicMock()
        primary.send.return_value = False
        fallback = MagicMock()
        fallback.send.return_value = False
        svc = FallbackEmailService(primary, fallback)

        ok = svc.send(email_message())

        assert ok is False
        fallback.send.assert_called_once()

    def test_forwards_full_payload_to_fallback(self):
        primary = MagicMock()
        primary.send.return_value = False
        fallback = FakeEmailService()
        svc = FallbackEmailService(primary, fallback)

        svc.send(email_message(
            to=['ops@base.local'],
            subject='Invoice',
            html_body='<p>PDF</p>',
            plain_body='PDF',
            from_email='noreply@base.local',
            from_name='Base',
            cc=['cc@base.local'],
            bcc=['bcc@base.local'],
            reply_to='soporte@base.local',
            attachments=[EmailAttachment(filename='a.pdf', content='Zm9v')],
        ))

        payload = fallback.sent[0]
        assert payload.to == ['ops@base.local']
        assert payload.cc == ['cc@base.local']
        assert payload.reply_to == 'soporte@base.local'
        assert payload.attachments[0].filename == 'a.pdf'
