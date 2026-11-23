"""Unit tests de RedisSessionLogBuffer (anillo por sesión) con un Redis falso."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import patch

from platform.features.support.incidents.incident.domain.schemas import TransactionLogEntry
from platform.features.support.incidents.incident.infrastructure import redis_buffer
from platform.features.support.incidents.incident.infrastructure.redis_buffer import (
    RedisSessionLogBuffer,
)


class _FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def lpush(self, key, value):
        self._ops.append(('lpush', key, value))
        return self

    def ltrim(self, key, start, end):
        self._ops.append(('ltrim', key, start, end))
        return self

    def expire(self, key, ttl):
        self._ops.append(('expire', key, ttl))
        return self

    def execute(self):
        for op in self._ops:
            getattr(self._redis, op[0])(*op[1:])
        self._ops = []


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    def lpush(self, key, value):
        self.store.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        data = self.store.get(key, [])
        self.store[key] = data[start:end + 1]

    def expire(self, key, ttl):
        self.ttls[key] = ttl

    def lrange(self, key, start, end):
        data = self.store.get(key, [])
        if end == -1:
            return data[start:]
        return data[start:end + 1]

    def pipeline(self):
        return _FakePipeline(self)


def _entry(request_id, logs=None):
    return TransactionLogEntry(
        request_id=request_id, ts='2026-07-01T10:00:00+00:00',
        method='GET', path=f'/x/{request_id}', logs=logs or [],
    )


class RedisSessionLogBufferTests(TestCase):

    def setUp(self):
        self.fake = FakeRedis()
        self.patcher = patch.object(redis_buffer, '_get_client', return_value=self.fake)
        self.patcher.start()
        self.buffer = RedisSessionLogBuffer()

    def tearDown(self):
        self.patcher.stop()

    def test_append_then_snapshot_roundtrip(self):
        self.buffer.append_transaction('sid', _entry('r1', logs=['a']))
        snap = self.buffer.snapshot('sid')
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap[0]['request_id'], 'r1')
        self.assertEqual(snap[0]['logs'], ['a'])

    def test_keeps_only_ring_size_and_chronological_order(self):
        n = self.buffer._ring_size
        for i in range(n + 5):          # empujar más del tope
            self.buffer.append_transaction('sid', _entry(f'r{i}'))
        snap = self.buffer.snapshot('sid')
        self.assertEqual(len(snap), n)
        # Orden cronológico: la más antigua retenida primero, la última al final
        self.assertEqual(snap[-1]['request_id'], f'r{n + 4}')
        self.assertEqual(snap[0]['request_id'], f'r{5}')

    def test_sets_ttl(self):
        self.buffer.append_transaction('sid', _entry('r1'))
        self.assertEqual(self.fake.ttls['sess_txns:sid'], self.buffer._ttl)

    def test_empty_session_id_is_noop(self):
        self.buffer.append_transaction('', _entry('r1'))
        self.assertEqual(self.fake.store, {})
        self.assertEqual(self.buffer.snapshot(''), [])

    def test_oversized_entry_is_shrunk(self):
        self.buffer._max_bytes = 300          # fuerza el shrink
        big_logs = [f'linea-de-log-numero-{i}' for i in range(200)]
        self.buffer.append_transaction('sid', _entry('r1', logs=big_logs))
        snap = self.buffer.snapshot('sid')
        self.assertEqual(len(snap), 1)
        # Debe haber recortado logs y dejado el marcador
        self.assertLess(len(snap[0]['logs']), len(big_logs))
        self.assertIn('… (entrada truncada por tamaño)', snap[0]['logs'])

    def test_snapshot_survives_redis_failure(self):
        with patch.object(redis_buffer, '_get_client', side_effect=RuntimeError('down')):
            self.assertEqual(self.buffer.snapshot('sid'), [])
            # append tampoco propaga
            self.buffer.append_transaction('sid', _entry('r1'))
