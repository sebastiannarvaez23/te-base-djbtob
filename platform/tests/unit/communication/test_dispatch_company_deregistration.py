"""Unit tests for COMPANY_DEREGISTRATION dispatcher context."""
from datetime import datetime, timezone as dt_timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.communication.notification.dispatchers import (
    dispatch_company_deregistration,
    format_company_document,
    format_deactivation_date,
)


class TestCompanyDeregistrationFormatting(TestCase):
    def test_formats_colombian_nit(self):
        self.assertEqual(format_company_document('9001234567'), '900.123.456-7')
        self.assertEqual(format_company_document('900.123.456-7'), '900.123.456-7')

    def test_formats_spanish_deactivation_date(self):
        dt = datetime(2026, 9, 15, 15, 42, tzinfo=dt_timezone.utc)
        text = format_deactivation_date(dt)
        self.assertIn('de septiembre de 2026', text)
        self.assertTrue(text.startswith('15 de septiembre de 2026, '))
        self.assertTrue(text.endswith('a. m.') or text.endswith('p. m.'))


class TestDispatchCompanyDeregistration(TestCase):
    @patch('platform.features.communication.notification.dispatchers.threading.Thread')
    @patch('platform.features.communication.notification.dispatchers.NotificationService')
    @patch(
        'platform.features.communication.notification.dispatchers.settings',
    )
    def test_sends_real_template_context(self, mock_settings, MockService, MockThread):
        mock_settings.PLATFORM_SUPPORT_EMAIL = 'soporte@base.local'
        user = MagicMock(
            first_name='Carlos',
            last_name='Rodríguez',
            username='carlos',
            email='carlos@maquinas.com',
        )
        closed_at = datetime(2026, 9, 15, 15, 42, tzinfo=dt_timezone.utc)

        dispatch_company_deregistration(
            user=user,
            company_name='Máquinas del Valle S.A.S.',
            company_nit='9001234567',
            closed_at=closed_at,
            reason='Solicitud del administrador',
        )

        MockThread.assert_called_once()
        MockThread.call_args.kwargs['target']()
        kwargs = MockService.return_value.send_email.call_args.kwargs
        self.assertEqual(kwargs['template_code'], 'COMPANY_DEREGISTRATION')
        self.assertEqual(kwargs['to'], ['carlos@maquinas.com'])
        ctx = kwargs['context']
        self.assertEqual(ctx['user_name'], 'Carlos Rodríguez')
        self.assertEqual(ctx['company_name'], 'Máquinas del Valle S.A.S.')
        self.assertEqual(ctx['company_document'], '900.123.456-7')
        self.assertEqual(ctx['deactivation_reason'], 'Solicitud del administrador')
        self.assertEqual(ctx['support_email'], 'soporte@base.local')
        self.assertEqual(ctx['current_year'], datetime.now().year)
        self.assertIn('de septiembre de 2026', ctx['deactivation_date'])
