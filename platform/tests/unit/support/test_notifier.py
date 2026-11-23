"""Unit tests de CeleryIncidentNotifier (encolado best-effort)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.support.incidents.incident.domain.schemas import IncidentView
from platform.features.support.incidents.incident.infrastructure.notifier import CeleryIncidentNotifier

_INCIDENT = IncidentView(id='inc-1', code='INC-2026-0001', status='open', severity='high')
_TASK = 'platform.features.support.incidents.incident.tasks.notify_incident_created'


class CeleryIncidentNotifierTests(TestCase):

    @patch(_TASK)
    def test_enqueues_celery_task(self, mock_task):
        mock_task.delay = MagicMock()
        CeleryIncidentNotifier().notify_created(_INCIDENT)
        mock_task.delay.assert_called_once_with('inc-1')

    @patch(_TASK)
    def test_survives_enqueue_failure(self, mock_task):
        mock_task.delay.side_effect = RuntimeError('broker down')
        CeleryIncidentNotifier().notify_created(_INCIDENT)
