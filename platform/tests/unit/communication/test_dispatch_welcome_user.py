"""Unit tests for dispatch_welcome_user."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.communication.notification.dispatchers import dispatch_welcome_user


class TestDispatchWelcomeUser(TestCase):

    @patch('platform.features.communication.notification.dispatchers.settings')
    @patch('platform.features.communication.notification.dispatchers.threading.Thread')
    @patch('platform.features.communication.notification.dispatchers.NotificationService')
    @patch('client.features.security.lifecycle.auth.application.password_recovery.IssuePasswordRecoveryTokenUseCase')
    @patch('core.parameters.get_parameter', return_value=45)
    def test_builds_context_and_sends_welcome_user(
        self, _param, MockIssueToken, MockService, MockThread, mock_settings,
    ):
        mock_settings.USER_ACTIVATION_URL = (
            'http://app.base.local:4110/security/activate-account'
        )
        mock_settings.PLATFORM_SUPPORT_EMAIL = 'soporte@warehouse-anywhere.com'
        MockIssueToken.return_value.execute.return_value = 'raw-token-abc'
        user = MagicMock(
            first_name='Natalia',
            last_name='Herrera',
            username='natalia',
            email='natalia.herrera@logisticaexpress.com',
        )
        company = MagicMock()
        company.name = 'Logística Express del Valle S.A.S'

        dispatch_welcome_user(user=user, company=company)

        MockIssueToken.assert_called_once_with(ttl_minutes=45)
        MockIssueToken.return_value.execute.assert_called_once_with(user)
        MockThread.assert_called_once()
        send_fn = MockThread.call_args.kwargs['target']
        send_fn()

        MockService.return_value.send_email.assert_called_once()
        kwargs = MockService.return_value.send_email.call_args.kwargs
        self.assertEqual(kwargs['template_code'], 'WELCOME_USER')
        self.assertEqual(kwargs['to'], ['natalia.herrera@logisticaexpress.com'])
        ctx = kwargs['context']
        self.assertEqual(ctx['user_name'], 'Natalia Herrera')
        self.assertEqual(ctx['user_email'], 'natalia.herrera@logisticaexpress.com')
        self.assertEqual(ctx['company_name'], company.name)
        self.assertEqual(ctx['support_email'], 'soporte@warehouse-anywhere.com')
        self.assertEqual(ctx['expiration_time'], 45)
        self.assertEqual(
            ctx['activation_url'],
            'http://app.base.local:4110/security/activate-account?token=raw-token-abc',
        )
