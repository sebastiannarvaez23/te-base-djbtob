"""Unit tests de SmtpEmailService."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from core.email.domain.schemas import EmailAttachment
from core.email.infrastructure.smtp import SmtpEmailService
from core.tests.unit.email.helpers import email_message

pytestmark = pytest.mark.unit

SMTP_PATH = 'necore.email.infrastructure.smtp'


class TestSmtpEmailService:

    def setup_method(self):
        self.service = SmtpEmailService()

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_sends_email_successfully(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        result = self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
        ))

        assert result is True
        mock_msg.attach_alternative.assert_called_once_with('<p>Test</p>', 'text/html')
        mock_msg.send.assert_called_once_with(fail_silently=False)

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_returns_false_on_send_error(self, MockEmail):
        mock_msg = MagicMock()
        mock_msg.send.side_effect = Exception('SMTP error')
        MockEmail.return_value = mock_msg

        result = self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
        ))
        assert result is False

    @override_settings(DEFAULT_FROM_EMAIL='default@platform.com', EMAIL_FROM_NAME='')
    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_uses_default_from_email_when_not_provided(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            from_email='',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['from_email'] == 'default@platform.com'

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_formats_sender_with_name(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            from_email='noreply@base.local',
            from_name='Base',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['from_email'] == 'Base <noreply@base.local>'

    @override_settings(DEFAULT_FROM_EMAIL='Base <noreply@base.local>', EMAIL_FROM_NAME='Base')
    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_keeps_preformatted_default_from(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['from_email'] == 'Base <noreply@base.local>'

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_passes_cc_and_bcc(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            cc=['cc@test.com'],
            bcc=['bcc@test.com'],
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['cc'] == ['cc@test.com']
        assert kwargs['bcc'] == ['bcc@test.com']

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_sets_reply_to(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            reply_to='soporte@base.local',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['reply_to'] == ['soporte@base.local']

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_empty_reply_to_gives_empty_list(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            reply_to='',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['reply_to'] == []

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_attaches_base64_file(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        content = base64.b64encode(b'PDF content').decode()

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            attachments=[EmailAttachment(
                filename='report.pdf',
                content=content,
                mimetype='application/pdf',
            )],
        ))

        mock_msg.attach.assert_called_once_with('report.pdf', b'PDF content', 'application/pdf')

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_skips_invalid_attachment(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='Test',
            html_body='<p>Test</p>',
            attachments=[EmailAttachment(
                filename='bad.pdf',
                content='!!!not-base64!!!',
                mimetype='application/pdf',
            )],
        ))

        mock_msg.attach.assert_not_called()

    @patch(f'{SMTP_PATH}.EmailMultiAlternatives')
    def test_uses_subject_as_plain_body_fallback(self, MockEmail):
        mock_msg = MagicMock()
        MockEmail.return_value = mock_msg

        self.service.send(email_message(
            to=['user@test.com'],
            subject='My Subject',
            html_body='<p>Test</p>',
            plain_body='',
        ))

        _, kwargs = MockEmail.call_args
        assert kwargs['body'] == 'My Subject'
