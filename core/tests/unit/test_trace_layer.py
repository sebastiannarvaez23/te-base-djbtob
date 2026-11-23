"""Unit tests for @trace_layer execution logs."""
import logging
from unittest import TestCase

import pytest

from core.trace import trace_layer

pytestmark = pytest.mark.unit


class _SampleUseCase:
    @trace_layer('application')
    def execute(self, value: int) -> int:
        return value + 1

    @trace_layer('application')
    def explode(self) -> None:
        raise ValueError('boom')


class TraceLayerTests(TestCase):

    def test_logs_start_and_success(self):
        with self.assertLogs('app.request', level=logging.DEBUG) as captured:
            result = _SampleUseCase().execute(2)
        self.assertEqual(result, 3)
        messages = [r.getMessage() for r in captured.records]
        self.assertTrue(any('┌ application → _SampleUseCase.execute' in m for m in messages))
        self.assertTrue(any('└ application ✓ _SampleUseCase.execute time=' in m for m in messages))

    def test_logs_failure(self):
        with self.assertLogs('app.request', level=logging.DEBUG) as captured:
            with self.assertRaises(ValueError):
                _SampleUseCase().explode()
        messages = [r.getMessage() for r in captured.records]
        self.assertTrue(any('┌ application → _SampleUseCase.explode' in m for m in messages))
        self.assertTrue(any('└ application ✗ _SampleUseCase.explode error=ValueError' in m for m in messages))
