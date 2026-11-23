from unittest.mock import MagicMock, patch

import pytest

from core.cache.invalidation import _cache, bump_versions, invalidate_cache, new_version

pytestmark = pytest.mark.unit

MODULE = 'core.cache.invalidation'


def test_bumps_all_versions_in_one_call_after_commit():
    cache, pending = MagicMock(), []
    with patch(f'{MODULE}._cache', return_value=cache), \
            patch(f'{MODULE}.transaction.on_commit', pending.append):
        bump_versions((key for key in ('a:v', 'b:v')), timeout=60)
        cache.set_many.assert_not_called()
        pending[0]()

    versions = cache.set_many.call_args.args[0]
    assert set(versions) == {'a:v', 'b:v'}
    assert versions['a:v'] != versions['b:v']
    assert cache.set_many.call_args.kwargs == {'timeout': 60}


def test_no_versions_is_a_noop():
    with patch(f'{MODULE}.transaction.on_commit') as on_commit:
        bump_versions([], timeout=60)
    on_commit.assert_not_called()


def test_bump_failure_is_logged_not_raised():
    cache = MagicMock()
    cache.set_many.side_effect = ConnectionError('redis down')
    with patch(f'{MODULE}._cache', return_value=cache), \
            patch(f'{MODULE}.transaction.on_commit', lambda fn: fn()), \
            patch(f'{MODULE}.logger') as logger:
        bump_versions(['a:v'], timeout=60)

    logger.warning.assert_called_once()


def test_new_versions_never_repeat():
    assert len({new_version() for _ in range(50)}) == 50


def test_access_cache_is_used():
    with patch(f'{MODULE}.caches', {'access': 'redis-access'}):
        assert _cache() == 'redis-access'


@pytest.mark.parametrize('pattern, method', [('params:*', 'delete_pattern'), ('params:all', 'delete')])
def test_invalidate_cache_by_pattern_or_exact_key(pattern, method):
    cache = MagicMock()
    with patch(f'{MODULE}._cache', return_value=cache):
        invalidate_cache(pattern)
    getattr(cache, method).assert_called_once_with(pattern)


def test_invalidate_cache_failure_is_logged_not_raised():
    cache = MagicMock()
    cache.delete.side_effect = ConnectionError('redis down')
    with patch(f'{MODULE}._cache', return_value=cache), patch(f'{MODULE}.logger') as logger:
        invalidate_cache('params:all')
    logger.warning.assert_called_once()
