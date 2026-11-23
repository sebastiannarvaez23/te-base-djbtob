"""
Unit tests for core/cache – use_case_cache decorator and invalidate_cache.

Covers:
- Cache HIT returns stored value without executing the function
- Cache MISS executes the function and stores the result
- Key built automatically from prefix + arguments
- No-args method uses prefix alone as key
- Graceful degradation when Redis read fails
- Graceful degradation when Redis write fails
- invalidate_cache with exact key
- invalidate_cache with wildcard pattern (delete_pattern)
- Graceful degradation when invalidation fails
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.cache.decorators import use_case_cache, TTL
from core.cache.invalidation import invalidate_cache


# ── Helpers ──────────────────────────────────────────────────────────────────


class _DummyUseCase:
    """Minimal use case to exercise the decorator."""

    def __init__(self):
        self.call_count = 0

    @use_case_cache(prefix='items')
    def list_all(self):
        self.call_count += 1
        return ['a', 'b', 'c']

    @use_case_cache(prefix='items')
    def get_by_id(self, item_id):
        self.call_count += 1
        return {'id': item_id, 'name': 'thing'}


# ── use_case_cache decorator ────────────��───────────────────────────────────


class TestUseCaseCacheHit(TestCase):
    """When the value is already in Redis, the wrapped function must NOT run."""

    @patch('core.cache.decorators.caches')
    def test_returns_cached_value_without_executing(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = ['cached']

        uc = _DummyUseCase()
        result = uc.list_all()

        self.assertEqual(result, ['cached'])
        self.assertEqual(uc.call_count, 0)
        mock_cache.get.assert_called_once_with('items')
        mock_cache.set.assert_not_called()


class TestUseCaseCacheMiss(TestCase):
    """When Redis returns None, the function executes and stores the result."""

    @patch('core.cache.decorators.caches')
    def test_executes_and_stores_result(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None

        uc = _DummyUseCase()
        result = uc.list_all()

        self.assertEqual(result, ['a', 'b', 'c'])
        self.assertEqual(uc.call_count, 1)
        mock_cache.set.assert_called_once_with('items', ['a', 'b', 'c'], timeout=TTL)


class TestUseCaseCacheDynamicKey(TestCase):
    """When method has arguments, the key is prefix:arg1:arg2."""

    @patch('core.cache.decorators.caches')
    def test_builds_key_from_prefix_and_args(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None

        uc = _DummyUseCase()
        uc.get_by_id('abc-123')

        mock_cache.get.assert_called_once_with('items:abc-123')
        mock_cache.set.assert_called_once_with(
            'items:abc-123', {'id': 'abc-123', 'name': 'thing'}, timeout=TTL,
        )

    @patch('core.cache.decorators.caches')
    def test_cache_hit_with_dynamic_key(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = {'id': 'abc-123', 'name': 'cached-thing'}

        uc = _DummyUseCase()
        result = uc.get_by_id('abc-123')

        self.assertEqual(result, {'id': 'abc-123', 'name': 'cached-thing'})
        self.assertEqual(uc.call_count, 0)


class TestUseCaseCacheKwargKey(TestCase):
    """La clave con kwargs es cualificada por nombre y ordenada, así no
    depende del orden en que se pasen ni colisiona con posicionales."""

    @patch('core.cache.decorators.caches')
    def test_kwargs_key_is_name_qualified_and_order_independent(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None

        class _UC:
            @use_case_cache(prefix='p')
            def m(self, **kwargs):
                return 'r'

        # kwargs en orden inverso → misma clave 'p:a=1:b=2'.
        _UC().m(b=2, a=1)

        mock_cache.get.assert_called_once_with('p:a=1:b=2')
        mock_cache.set.assert_called_once_with('p:a=1:b=2', 'r', timeout=TTL)


class TestUseCaseCacheGracefulDegradation(TestCase):
    """When Redis fails, the function still executes normally."""

    @patch('core.cache.decorators.caches')
    def test_executes_when_cache_read_fails(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.side_effect = ConnectionError('Redis down')

        uc = _DummyUseCase()
        result = uc.list_all()

        self.assertEqual(result, ['a', 'b', 'c'])
        self.assertEqual(uc.call_count, 1)

    @patch('core.cache.decorators.caches')
    def test_returns_result_when_cache_write_fails(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = ConnectionError('Redis down')

        uc = _DummyUseCase()
        result = uc.list_all()

        self.assertEqual(result, ['a', 'b', 'c'])
        self.assertEqual(uc.call_count, 1)


# ── invalidate_cache ───────────────────���────────────────────────────────────


class TestInvalidateCacheExactKey(TestCase):

    @patch('core.cache.invalidation.caches')
    def test_deletes_exact_key(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

        invalidate_cache('parameters:all')

        mock_cache.delete.assert_called_once_with('parameters:all')
        mock_cache.delete_pattern.assert_not_called()


class TestInvalidateCacheWildcard(TestCase):

    @patch('core.cache.invalidation.caches')
    def test_uses_delete_pattern_for_wildcard(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)

        invalidate_cache('parameters:*')

        mock_cache.delete_pattern.assert_called_once_with('parameters:*')
        mock_cache.delete.assert_not_called()


class TestInvalidateCacheGracefulDegradation(TestCase):

    @patch('core.cache.invalidation.caches')
    def test_does_not_raise_when_redis_fails(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.delete_pattern.side_effect = ConnectionError('Redis down')

        invalidate_cache('parameters:*')  # no exception raised

    @patch('core.cache.invalidation.caches')
    def test_does_not_raise_on_exact_key_failure(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.delete.side_effect = ConnectionError('Redis down')

        invalidate_cache('parameters:all')  # no exception raised
