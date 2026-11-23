"""Unit tests de ResendEmailService (SDK mockeado, sin red)."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from core.email.domain.schemas import EmailAttachment
from core.email.infrastructure.resend import ResendEmailService
from core.errors import AppErrorCode, ServerException
from core.tests.unit.email.helpers import email_message

pytestmark = pytest.mark.unit


class TestResendEmailService:

    def setup_method(self):
        self.service = ResendEmailService(api_key='re_test')

    def test_requires_api_key(self):
        with pytest.raises(ServerException) as exc:
            ResendEmailService(api_key='')
        assert exc.value.code == AppErrorCode.EMAIL_PROVIDER_UNAVAILABLE

    @override_settings(
        DEFAULT_FROM_EMAIL='Base <noreply@base.local>',
        EMAIL_FROM_NAME='Base',
    )
    def test_sends_payload_and_returns_true(self):
        self.service._send = MagicMock(return_value={'id': 'em_1'})

        ok = self.service.send(email_message(
            to=['ops@base.local'],
            subject='Welcome',
            html_body='<p>Hi</p>',
            plain_body='Hi',
            from_email='noreply@base.local',
            from_name='Base',
            reply_to='soporte@base.local',
            cc=['cc@base.local'],
            bcc=['bcc@base.local'],
        ))

        assert ok is True
        params = self.service._send.call_args[0][0]
        assert params['from'] == 'Base <noreply@base.local>'
        assert params['to'] == ['ops@base.local']
        assert params['subject'] == 'Welcome'
        assert params['html'] == '<p>Hi</p>'
        assert params['text'] == 'Hi'
        assert params['reply_to'] == 'soporte@base.local'
        assert params['cc'] == ['cc@base.local']
        assert params['bcc'] == ['bcc@base.local']
        assert params['tags'] == [{'name': 'app', 'value': 'base'}]

    @override_settings(
        DEFAULT_FROM_EMAIL='Base <noreply@base.local>',
        EMAIL_FROM_NAME='Base',
    )
    def test_uses_default_from_when_empty(self):
        self.service._send = MagicMock(return_value={'id': 'em_2'})

        self.service.send(email_message(
            to=['ops@base.local'],
            subject='Hi',
            html_body='<p>Hi</p>',
        ))

        params = self.service._send.call_args[0][0]
        assert params['from'] == 'Base <noreply@base.local>'

    def test_returns_false_on_provider_error(self):
        self.service._send = MagicMock(side_effect=RuntimeError('timeout'))

        ok = self.service.send(email_message(
            to=['ops@base.local'],
            subject='Hi',
            html_body='<p>Hi</p>',
        ))
        assert ok is False

    @override_settings(DEFAULT_FROM_EMAIL='', EMAIL_FROM_NAME='')
    def test_skips_when_no_from(self):
        self.service._send = MagicMock()
        ok = self.service.send(email_message(to=['ops@base.local'], from_email=''))
        assert ok is False
        self.service._send.assert_not_called()

    def test_forwards_base64_attachments(self):
        self.service._send = MagicMock(return_value={'id': 'em_3'})

        self.service.send(email_message(
            to=['ops@base.local'],
            subject='Invoice',
            html_body='<p>PDF</p>',
            attachments=[EmailAttachment(
                filename='invoice.pdf',
                content='Zm9v',
                mimetype='application/pdf',
            )],
        ))

        params = self.service._send.call_args[0][0]
        assert params['attachments'] == [{
            'filename': 'invoice.pdf',
            'content': 'Zm9v',
            'content_type': 'application/pdf',
        }]

    def test_missing_sdk_raises_server_exception(self):
        with patch.dict('sys.modules', {'resend': None}):
            with pytest.raises(ServerException) as exc:
                self.service.send(email_message(
                    to=['ops@base.local'],
                    from_email='noreply@base.local',
                ))
        assert exc.value.code == AppErrorCode.EMAIL_PROVIDER_UNAVAILABLE

    @override_settings(
        DEFAULT_FROM_EMAIL='Base <noreply@base.local>',
        EMAIL_FROM_NAME='Base',
    )
    def test_send_sets_sdk_api_key(self):
        fake_resend = MagicMock()
        fake_resend.Emails.send.return_value = {'id': 'em_sdk'}

        with patch.dict('sys.modules', {'resend': fake_resend}):
            svc = ResendEmailService(api_key='re_live')
            ok = svc.send(email_message(
                to=['ops@base.local'],
                subject='Hi',
                html_body='<p>Hi</p>',
            ))

        assert ok is True
        assert fake_resend.api_key == 're_live'
        fake_resend.Emails.send.assert_called_once()
