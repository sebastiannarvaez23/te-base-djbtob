"""Unit tests: BaseTask materializa incidencia al fallar (solo logs de tarea)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from core.task_trace import drain_task_logs, peek_task_logs
from core.tasks.base import BaseTask

pytestmark = pytest.mark.unit


class _DemoTask(BaseTask):
    name = 'demo.failing_task'


class BaseTaskIncidentHookTests(TestCase):

    def tearDown(self):
        drain_task_logs()

    def test_before_start_opens_task_log_capture(self):
        from core.task_trace import is_task_capturing

        task = _DemoTask()
        task.before_start('tid-10', (), {'schema_name': 'acme'})
        self.assertTrue(is_task_capturing())
        self.assertEqual(peek_task_logs(), [])

    @patch('core.tasks.incident_port.report_task_incident')
    def test_on_failure_reports_incident_with_peeked_logs(self, mock_report):
        task = _DemoTask()
        task.before_start('tid-11', (), {'schema_name': 'acme'})
        from core.task_trace import append_task_log
        append_task_log('only-task-log', 100)

        einfo = SimpleNamespace(traceback='Traceback (most recent call last):\n...')
        task.on_failure(RuntimeError('boom'), 'tid-11', (), {'schema_name': 'acme'}, einfo)

        mock_report.assert_called_once()
        kwargs = mock_report.call_args.kwargs
        self.assertEqual(kwargs['task_id'], 'tid-11')
        self.assertEqual(kwargs['task_name'], 'demo.failing_task')
        self.assertEqual(kwargs['schema_name'], 'acme')
        self.assertIn('only-task-log', kwargs['task_logs'])
        self.assertTrue(any('task_failed' in line for line in kwargs['task_logs']))
        self.assertIn('Traceback', kwargs['traceback_text'])

    @patch('core.tasks.incident_port.report_task_incident')
    def test_after_return_drains_buffer(self, _mock_report):
        task = _DemoTask()
        task.before_start('tid-12', (), {})
        from core.task_trace import append_task_log, is_task_capturing
        append_task_log('x', 10)
        task.after_return('FAILURE', None, 'tid-12', (), {}, None)
        self.assertFalse(is_task_capturing())

    @patch('core.tasks.incident_port.report_task_incident')
    def test_report_failure_is_swallowed(self, mock_report):
        mock_report.side_effect = RuntimeError('db down')
        task = _DemoTask()
        task.before_start('tid-13', (), {})
        # Must not raise
        task.on_failure(ValueError('orig'), 'tid-13', (), {}, None)
