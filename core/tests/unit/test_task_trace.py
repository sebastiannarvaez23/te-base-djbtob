"""Unit tests del buffer de logs por tarea Celery (core.task_trace)."""
import logging
from unittest import TestCase

import pytest

from core.task_trace import (
    TASK_LOG_TRUNCATED,
    append_task_log,
    drain_task_logs,
    get_task_meta,
    is_task_capturing,
    peek_task_logs,
    start_task_capture,
)

pytestmark = pytest.mark.unit


class TaskTraceBufferTests(TestCase):

    def tearDown(self):
        drain_task_logs()

    def test_not_capturing_by_default(self):
        drain_task_logs()
        self.assertFalse(is_task_capturing())
        append_task_log('x', 10)
        self.assertEqual(drain_task_logs(), [])

    def test_capture_collects_only_task_lines(self):
        start_task_capture(task_id='t1', task_name='subscription.renew_due_subscriptions')
        append_task_log('a', 10)
        append_task_log('b', 10)
        self.assertEqual(peek_task_logs(), ['a', 'b'])
        self.assertEqual(get_task_meta()['task_name'], 'subscription.renew_due_subscriptions')
        self.assertEqual(drain_task_logs(), ['a', 'b'])
        self.assertFalse(is_task_capturing())

    def test_respects_max_lines(self):
        start_task_capture()
        for i in range(5):
            append_task_log(f'line-{i}', max_lines=2)
        result = drain_task_logs()
        self.assertEqual(result, ['line-0', 'line-1', TASK_LOG_TRUNCATED])


class TaskBufferingLogHandlerTests(TestCase):

    def setUp(self):
        from core.logging_handlers import TaskBufferingLogHandler
        self.handler = TaskBufferingLogHandler(max_lines=100)
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger = logging.getLogger('test.task.incident.buffer')
        self.logger.handlers = [self.handler]
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def tearDown(self):
        drain_task_logs()
        self.logger.handlers = []

    def test_handler_noop_without_capture(self):
        self.logger.info('ignored')
        self.assertEqual(peek_task_logs(), [])

    def test_handler_appends_while_capturing(self):
        start_task_capture(task_id='t2', task_name='demo.task')
        self.logger.info('from-task')
        self.assertEqual(peek_task_logs(), ['from-task'])
