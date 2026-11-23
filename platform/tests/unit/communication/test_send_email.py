"""
Unit tests for SendEmailUseCase.

No database required — pure logic tests with mocked dependencies.
The email transport adapters live in core/tests/unit/email/.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.email.domain.schemas import SendEmailMessage
from core.errors.exceptions import NotFoundException, ConflictException, ServerException
from core.errors.codes import AppErrorCode
from platform.features.communication.email.email_template.application.use_cases import SendEmailUseCase
from platform.features.communication.email.email_template.domain.schemas import (
    EmailTemplateSchema,
    SendEmailSchema,
)
from platform.features.communication.email.email_sender.domain.schemas import EmailSenderSchema

pytestmark = pytest.mark.unit


def _sent(mock) -> SendEmailMessage:
    return mock.send.call_args.args[0]


def _template(**overrides) -> EmailTemplateSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='WELCOME',
        name='Welcome',
        subject='Hello {{ name }}',
        body='Plain hello {{ name }}',
        html_template='<h1>Hello {{ name }}</h1>',
        sender=None,
        is_active=True,
    )
    defaults.update(overrides)
    return EmailTemplateSchema(**defaults)


def _sender(**overrides) -> EmailSenderSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='MAIN',
        name='Platform',
        email='noreply@platform.com',
        reply_to='support@platform.com',
        is_default=True,
        is_active=True,
    )
    defaults.update(overrides)
    return EmailSenderSchema(**defaults)


def _send_data(**overrides) -> SendEmailSchema:
    defaults = dict(
        template_code='WELCOME',
        to=['user@example.com'],
        context={'name': 'John'},
    )
    defaults.update(overrides)
    return SendEmailSchema(**defaults)


# ── SendEmailUseCase ──────────────────────────────────────────────────────────

class TestSendEmailUseCase(TestCase):

    def setUp(self):
        self.template_repo = MagicMock()
        self.sender_repo = MagicMock()
        self.email_service = MagicMock()
        self.uc = SendEmailUseCase(
            repository=self.template_repo,
            sender_repository=self.sender_repo,
            email_service=self.email_service,
        )

    # ── Template resolution ──────────────────────────────────────────────

    def test_raises_not_found_when_template_missing(self):
        self.template_repo.get_by_code.return_value = None
        data = _send_data()

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND)

    def test_raises_conflict_when_template_inactive(self):
        self.template_repo.get_by_code.return_value = _template(is_active=False)
        data = _send_data()

        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_TEMPLATE_INACTIVE)

    # ── Template rendering ───────────────────────────────────────────────

    def test_renders_subject_with_context(self):
        tpl = _template(subject='Hi {{ name }}')
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'name': 'Ana'}))

        self.assertEqual(_sent(self.email_service).subject, 'Hi Ana')

    def test_renders_html_body_with_context(self):
        tpl = _template(html_template='<p>Welcome {{ name }}</p>')
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'name': 'Ana'}))

        self.assertEqual(_sent(self.email_service).html_body, '<p>Welcome Ana</p>')

    def test_renders_html_when_variable_tag_is_split_across_newlines(self):
        tpl = _template(html_template='<p>Hola <strong>{{ user_name\n                                    }}</strong>,</p>')
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'user_name': 'Carlos Rodríguez'}))

        html = _sent(self.email_service).html_body
        self.assertIn('Carlos Rodríguez', html)
        self.assertNotIn('{{ user_name }}', html)
        self.assertNotIn('{{', html)

    def test_renders_plain_body_with_context(self):
        tpl = _template(body='Hello {{ name }}')
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'name': 'Ana'}))

        self.assertEqual(_sent(self.email_service).plain_body, 'Hello Ana')

    def test_plain_body_empty_when_template_body_empty(self):
        tpl = _template(body='')
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        self.assertEqual(_sent(self.email_service).plain_body, '')

    def test_raises_server_exception_on_render_error(self):
        tpl = _template(subject='{{ invalid_tag|bad_filter }}')
        self.template_repo.get_by_code.return_value = tpl

        with self.assertRaises(ServerException) as ctx:
            self.uc.execute(_send_data())
        self.assertEqual(ctx.exception.code, AppErrorCode.EMAIL_RENDER_ERROR)

    # ── Sender resolution ────────────────────────────────────────────────

    def test_uses_template_sender_when_present(self):
        sender_id = uuid.uuid4()
        sender = _sender(id=sender_id)
        tpl = _template(sender=sender_id)
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_by_id.return_value = sender
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        msg = _sent(self.email_service)
        self.assertEqual(msg.from_email, sender.email)
        self.assertEqual(msg.from_name, sender.name)
        self.assertEqual(msg.reply_to, sender.reply_to)

    def test_falls_back_to_default_sender(self):
        default = _sender(is_default=True)
        tpl = _template(sender=None)
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = default
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        msg = _sent(self.email_service)
        self.assertEqual(msg.from_email, default.email)
        self.assertEqual(msg.from_name, default.name)

    def test_empty_sender_when_no_sender_resolved(self):
        tpl = _template(sender=None)
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        msg = _sent(self.email_service)
        self.assertEqual(msg.from_email, '')
        self.assertEqual(msg.from_name, '')

    def test_empty_sender_when_template_sender_not_found(self):
        sender_id = uuid.uuid4()
        tpl = _template(sender=sender_id)
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_by_id.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        self.assertEqual(_sent(self.email_service).from_email, '')

    # ── CC / BCC passthrough ─────────────────────────────────────────────

    def test_passes_cc_and_bcc_to_service(self):
        tpl = _template()
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        data = _send_data(cc=['cc@test.com'], bcc=['bcc@test.com'])
        self.uc.execute(data)

        msg = _sent(self.email_service)
        self.assertEqual(msg.cc, ['cc@test.com'])
        self.assertEqual(msg.bcc, ['bcc@test.com'])

    # ── mock_data is preview-only (not used on production send) ───────────

    def test_mock_data_is_not_used_on_send(self):
        """Missing context keys render blank — never filled from mock_data."""
        tpl = _template(subject='Hi {{ name }} from {{ company }}',
                        mock_data={'name': 'Sample', 'company': 'ACME'})
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'name': 'Ana'}))

        self.assertEqual(_sent(self.email_service).subject, 'Hi Ana from ')

    def test_context_is_used_as_data_layer(self):
        tpl = _template(subject='{{ greeting }}', mock_data={'greeting': 'MOCK'})
        self.template_repo.get_by_code.return_value = tpl
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data(context={'greeting': 'REAL'}))

        self.assertEqual(_sent(self.email_service).subject, 'REAL')

    # ── Attachments passthrough ──────────────────────────────────────────

    def test_forwards_attachments_to_service(self):
        self.template_repo.get_by_code.return_value = _template()
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        attachments = [{'filename': 'invoice.pdf', 'content': 'Zm9v', 'mimetype': 'application/pdf'}]
        self.uc.execute(_send_data(attachments=attachments))

        att = _sent(self.email_service).attachments[0]
        self.assertEqual(att.filename, 'invoice.pdf')
        self.assertEqual(att.content, 'Zm9v')
        self.assertEqual(att.mimetype, 'application/pdf')

    def test_no_attachments_passes_empty_list(self):
        self.template_repo.get_by_code.return_value = _template()
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        self.uc.execute(_send_data())

        self.assertEqual(_sent(self.email_service).attachments, [])

    # ── Return value ─────────────────────────────────────────────────────

    def test_returns_true_on_success(self):
        self.template_repo.get_by_code.return_value = _template()
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = True

        result = self.uc.execute(_send_data())
        self.assertTrue(result)

    def test_returns_false_when_service_fails(self):
        self.template_repo.get_by_code.return_value = _template()
        self.sender_repo.get_default.return_value = None
        self.email_service.send.return_value = False

        result = self.uc.execute(_send_data())
        self.assertFalse(result)
