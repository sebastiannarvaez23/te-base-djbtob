"""
Unit tests for NotificationService facade.

No database required — patches infrastructure dependencies.
"""
import uuid
from unittest import TestCase
from unittest.mock import patch, MagicMock

import pytest

from platform.features.communication.notification.service import NotificationService
from core.errors.exceptions import NotFoundException
from core.errors.codes import AppErrorCode

pytestmark = pytest.mark.unit


class TestNotificationService(TestCase):

    @patch('platform.features.communication.notification.service.get_email_service')
    @patch('platform.features.communication.notification.service.DjangoEmailSenderRepository')
    @patch('platform.features.communication.notification.service.DjangoEmailTemplateRepository')
    def setUp(self, MockTplRepo, MockSenderRepo, MockGetEmail):
        self.mock_tpl_repo = MockTplRepo.return_value
        self.mock_sender_repo = MockSenderRepo.return_value
        self.mock_email_svc = MockGetEmail.return_value
        self.svc = NotificationService()

    # ── Successful dispatch ───────────────────────────────────────────────

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_send_email_returns_true_on_success(self, MockUC):
        MockUC.return_value.execute.return_value = True

        result = self.svc.send_email(
            template_code='WELCOME',
            to=['user@test.com'],
            context={'name': 'John'},
        )
        self.assertTrue(result)

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_send_email_builds_schema_with_all_params(self, MockUC):
        MockUC.return_value.execute.return_value = True

        self.svc.send_email(
            template_code='RESET',
            to=['a@test.com', 'b@test.com'],
            context={'token': 'abc'},
            cc=['cc@test.com'],
            bcc=['bcc@test.com'],
            attachments=[{'filename': 'f.pdf', 'content': 'data'}],
        )

        schema = MockUC.return_value.execute.call_args[0][0]
        self.assertEqual(schema.template_code, 'RESET')
        self.assertEqual(schema.to, ['a@test.com', 'b@test.com'])
        self.assertEqual(schema.context, {'token': 'abc'})
        self.assertEqual(schema.cc, ['cc@test.com'])
        self.assertEqual(schema.bcc, ['bcc@test.com'])
        self.assertEqual(len(schema.attachments), 1)

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_send_email_defaults_optional_params(self, MockUC):
        MockUC.return_value.execute.return_value = True

        self.svc.send_email(
            template_code='WELCOME',
            to=['user@test.com'],
            context={},
        )

        schema = MockUC.return_value.execute.call_args[0][0]
        self.assertEqual(schema.cc, [])
        self.assertEqual(schema.bcc, [])
        self.assertEqual(schema.attachments, [])

    # ── Error handling ────────────────────────────────────────────────────

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_returns_false_when_use_case_raises(self, MockUC):
        MockUC.return_value.execute.side_effect = NotFoundException(
            AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
        )

        result = self.svc.send_email(
            template_code='MISSING',
            to=['user@test.com'],
            context={},
        )
        self.assertFalse(result)

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_returns_false_on_unexpected_exception(self, MockUC):
        MockUC.return_value.execute.side_effect = RuntimeError('unexpected')

        result = self.svc.send_email(
            template_code='WELCOME',
            to=['user@test.com'],
            context={},
        )
        self.assertFalse(result)

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_returns_false_when_send_fails(self, MockUC):
        MockUC.return_value.execute.return_value = False

        result = self.svc.send_email(
            template_code='WELCOME',
            to=['user@test.com'],
            context={},
        )
        self.assertFalse(result)

    # ── Wiring ────────────────────────────────────────────────────────────

    @patch('platform.features.communication.notification.service.SendEmailUseCase')
    def test_wires_repositories_into_use_case(self, MockUC):
        MockUC.return_value.execute.return_value = True

        self.svc.send_email(
            template_code='WELCOME',
            to=['user@test.com'],
            context={},
        )

        MockUC.assert_called_once()
        call_kwargs = MockUC.call_args[1]
        self.assertIn('repository', call_kwargs)
        self.assertIn('sender_repository', call_kwargs)
        self.assertIn('email_service', call_kwargs)
