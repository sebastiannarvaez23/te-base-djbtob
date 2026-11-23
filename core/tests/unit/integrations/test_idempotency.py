"""Matriz escenario 4 + chaos Redis — idempotencia."""

from unittest.mock import MagicMock, patch

import pytest

from core.integrations.infrastructure.idempotency import MemoryIdempotencyStore, RedisIdempotencyStore


@pytest.mark.unit
class TestMemoryIdempotencyStore:

    def test_put_and_get_round_trip(self):
        store = MemoryIdempotencyStore()
        store.put('scope', 'key', {'ok': True})
        assert store.get('scope', 'key') == {'ok': True}

    def test_missing_key_returns_none(self):
        assert MemoryIdempotencyStore().get('scope', 'missing') is None


@pytest.mark.unit
class TestRedisIdempotencyChaos:

    def test_get_degrades_when_redis_down(self):
        store = RedisIdempotencyStore()
        with patch('core.integrations.infrastructure.idempotency.caches') as mock_caches:
            mock_caches.__getitem__.side_effect = ConnectionError('redis down')
            assert store.get('tenant:conn', 'key') is None

    def test_put_degrades_when_redis_down(self):
        store = RedisIdempotencyStore()
        with patch('core.integrations.infrastructure.idempotency.caches') as mock_caches:
            mock_caches.__getitem__.side_effect = ConnectionError('redis down')
            store.put('tenant:conn', 'key', {'result': 'ok'})  # no exception
