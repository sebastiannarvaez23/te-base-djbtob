"""Unit tests del buffer de transacción por request (core.trace) y del
BufferingLogHandler que lo alimenta.
"""
import logging
from unittest import TestCase

from core.trace import (
    TXN_LOG_TRUNCATED,
    append_txn_log,
    drain_txn_logs,
    is_txn_capturing,
    start_txn_capture,
)


class TxnBufferTests(TestCase):

    def tearDown(self):
        drain_txn_logs()  # asegura reset entre tests

    def test_not_capturing_by_default(self):
        drain_txn_logs()
        self.assertFalse(is_txn_capturing())
        # append fuera de captura es no-op silencioso
        append_txn_log('x', 10)
        self.assertEqual(drain_txn_logs(), [])

    def test_capture_collects_lines_in_order(self):
        start_txn_capture()
        self.assertTrue(is_txn_capturing())
        append_txn_log('a', 10)
        append_txn_log('b', 10)
        self.assertEqual(drain_txn_logs(), ['a', 'b'])

    def test_drain_resets_capture(self):
        start_txn_capture()
        append_txn_log('a', 10)
        drain_txn_logs()
        self.assertFalse(is_txn_capturing())
        self.assertEqual(drain_txn_logs(), [])

    def test_respects_max_lines_with_single_marker(self):
        start_txn_capture()
        for i in range(5):
            append_txn_log(f'line-{i}', max_lines=3)
        result = drain_txn_logs()
        self.assertEqual(result, ['line-0', 'line-1', 'line-2', TXN_LOG_TRUNCATED])
        self.assertEqual(result.count(TXN_LOG_TRUNCATED), 1)


class BufferingLogHandlerTests(TestCase):

    def setUp(self):
        from core.logging_handlers import BufferingLogHandler
        self.handler = BufferingLogHandler(max_lines=100)
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger = logging.getLogger('test.incident.buffer')
        self.logger.handlers = [self.handler]
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def tearDown(self):
        drain_txn_logs()

    def test_captures_only_within_active_capture(self):
        # Sin captura activa: no acumula
        self.logger.info('fuera')
        self.assertEqual(drain_txn_logs(), [])

        start_txn_capture()
        self.logger.info('dentro-1')
        self.logger.info('dentro-2')
        self.assertEqual(drain_txn_logs(), ['dentro-1', 'dentro-2'])

    def test_skips_http_envelope_lines(self):
        start_txn_capture()
        self.logger.info('>> REQ origin=app method=POST path=/api/v1/x/')
        self.logger.info('  ┌ application → SaveOrder')
        self.logger.info('<< RES origin=app method=POST path=/api/v1/x/ status=200')
        self.logger.info('!! EXC path=/api/v1/x/ exc=ValueError')
        self.assertEqual(drain_txn_logs(), [
            '  ┌ application → SaveOrder',
            '!! EXC path=/api/v1/x/ exc=ValueError',
        ])
