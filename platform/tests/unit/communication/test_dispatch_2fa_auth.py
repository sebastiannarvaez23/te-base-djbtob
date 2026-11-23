"""Unit tests for the 2FA_AUTH dispatcher context."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.communication.notification.contexts import TwoFactorAuthContext
from platform.features.communication.notification.dispatchers import dispatch_2fa_auth


class TestDispatch2faAuth(TestCase):

    @patch('platform.features.communication.notification.dispatchers.threading.Thread')
    def test_builds_template_context(self, thread_cls):
        user = MagicMock()
        user.first_name = 'Sebastián'
        user.last_name = 'Gómez'
        user.username = 'sgomez'
        user.email = 'seb@base.local'

        captured = {}

        def _capture(*args, **kwargs):
            captured['target'] = kwargs.get('target') or (args[0] if args else None)
            return MagicMock()

        thread_cls.side_effect = _capture

        with patch(
            'platform.features.communication.notification.dispatchers.NotificationService'
        ) as svc_cls:
            dispatch_2fa_auth(
                user=user,
                otp_code='482931',
                login_ip='190.25.123.45',
                login_time='2026-03-30 14:32',
                login_device='Chrome - Windows',
                login_location='Cali, Colombia',
                expiration_time=5,
            )
            captured['target']()
            kwargs = svc_cls.return_value.send_email.call_args.kwargs
            self.assertEqual(kwargs['template_code'], '2FA_AUTH')
            self.assertEqual(kwargs['to'], ['seb@base.local'])
            ctx = TwoFactorAuthContext(**kwargs['context'])
            self.assertEqual(ctx.otp_code, '482931')
            self.assertEqual(ctx.login_ip, '190.25.123.45')
            self.assertEqual(ctx.user_name, 'Sebastián Gómez')
            self.assertEqual(ctx.login_device, 'Chrome - Windows')
            self.assertEqual(ctx.login_location, 'Cali, Colombia')
            self.assertEqual(ctx.expiration_time, 5)
            self.assertEqual(ctx.current_year, datetime.now().year)
