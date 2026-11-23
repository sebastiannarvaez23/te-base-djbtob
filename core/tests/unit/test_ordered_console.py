"""Unit tests for ordered console request buffering (by trace_id)."""
import io
import logging
import threading
from unittest import TestCase

import pytest

from core.logging_handlers import OrderedRequestConsoleHandler, _CONSOLE_BUFFERS

pytestmark = pytest.mark.unit


class OrderedRequestConsoleHandlerTests(TestCase):

    def setUp(self):
        self.stream = io.StringIO()
        self.handler = OrderedRequestConsoleHandler(stream=self.stream)
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger = logging.getLogger('test.ordered.console')
        self.logger.handlers = [self.handler]
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        _CONSOLE_BUFFERS.clear()

    def tearDown(self):
        _CONSOLE_BUFFERS.clear()

    def test_writes_immediately_without_open_buffer(self):
        self.logger.info('live', extra={'trace_id': 'orphan'})
        self.assertIn('live', self.stream.getvalue())

    def test_buffers_then_flushes_as_one_block(self):
        tid = 'req-a'
        OrderedRequestConsoleHandler.open_request(tid)
        self.logger.info('>> REQ', extra={'trace_id': tid})
        self.logger.debug('  ┌ application → Foo.execute', extra={'trace_id': tid})
        self.logger.debug('  └ application ✓ Foo.execute time=1.0ms', extra={'trace_id': tid})
        self.logger.info('<< RES', extra={'trace_id': tid})
        self.assertEqual(self.stream.getvalue(), '')

        OrderedRequestConsoleHandler.flush_request(tid, stream=self.stream)
        out = self.stream.getvalue()
        self.assertEqual(
            out,
            '>> REQ\n'
            '  ┌ application → Foo.execute\n'
            '  └ application ✓ Foo.execute time=1.0ms\n'
            '<< RES\n'
            '\n',
        )
        self.assertNotIn(tid, _CONSOLE_BUFFERS)

    def test_concurrent_requests_do_not_interleave(self):
        """Dos requests concurrentes vuelcan bloques contiguos, no líneas mezcladas."""
        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def run(tid: str, label: str):
            try:
                OrderedRequestConsoleHandler.open_request(tid)
                barrier.wait(timeout=2)
                for i in range(20):
                    self.logger.info('%s-%s', label, i, extra={'trace_id': tid})
                OrderedRequestConsoleHandler.flush_request(tid, stream=self.stream)
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        t1 = threading.Thread(target=run, args=('trace-1', 'A'))
        t2 = threading.Thread(target=run, args=('trace-2', 'B'))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        self.assertEqual(errors, [])

        out = self.stream.getvalue()
        lines = [ln for ln in out.splitlines() if ln]
        self.assertEqual(len(lines), 40)

        # Cada bloque A-* / B-* debe aparecer contiguo (20 líneas seguidas).
        def first_run(prefix: str) -> list[str]:
            start = next(i for i, ln in enumerate(lines) if ln.startswith(prefix))
            return lines[start : start + 20]

        block_a = first_run('A-')
        block_b = first_run('B-')
        self.assertEqual(block_a, [f'A-{i}' for i in range(20)])
        self.assertEqual(block_b, [f'B-{i}' for i in range(20)])

    def test_flush_uses_handler_bound_stream(self):
        tid = 'req-bound'
        OrderedRequestConsoleHandler.open_request(tid)
        self.logger.info('line', extra={'trace_id': tid})
        OrderedRequestConsoleHandler.flush_request(tid)  # no explicit stream
        self.assertIn('line', self.stream.getvalue())

    def test_truncates_oversized_buffer(self):
        from core import logging_handlers as lh
        tid = 'req-trunc'
        OrderedRequestConsoleHandler.open_request(tid)
        old = lh._CONSOLE_MAX_LINES
        try:
            lh._CONSOLE_MAX_LINES = 3
            for i in range(10):
                self.logger.info('L%s', i, extra={'trace_id': tid})
            OrderedRequestConsoleHandler.flush_request(tid, stream=self.stream)
            out = self.stream.getvalue()
            self.assertIn('L0', out)
            self.assertIn('L2', out)
            self.assertIn('console buffer truncated', out)
            self.assertNotIn('L9', out)
        finally:
            lh._CONSOLE_MAX_LINES = old
