"""Unit tests de tareas Celery del sistema de incidencias."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.support.incidents.incident.tasks import notify_incident_created

_MOD = 'platform.features.support.incidents.incident.models.Incident'


class NotifyIncidentCreatedTaskTests(TestCase):

    @patch(_MOD)
    def test_noop_when_incident_missing(self, mock_incident):
        mock_incident.objects.filter.return_value.first.return_value = None
        notify_incident_created.run('missing-id')
        mock_incident.objects.filter.assert_called_once()

    @patch('platform.features.support.incidents.incident.tasks.logging.getLogger')
    @patch(_MOD)
    def test_logs_incident_created_event(self, mock_incident, mock_get_logger):
        inc = MagicMock(
            code='INC-2026-0042',
            status='open',
            schema_name='arisoft',
            reporter_username='ana',
            trace_id='req-1',
            error={'path': '/api/v1/x/'},
        )
        mock_incident.objects.filter.return_value.first.return_value = inc
        errors_logger = MagicMock()
        mock_get_logger.return_value = errors_logger

        notify_incident_created.run('inc-uuid')

        errors_logger.warning.assert_called_once()
        args, kwargs = errors_logger.warning.call_args
        self.assertIn('INCIDENT_CREATED', args[0])
        self.assertEqual(args[1], 'INC-2026-0042')
        self.assertEqual(kwargs['extra']['trace_id'], 'req-1')
