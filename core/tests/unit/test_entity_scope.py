import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from enum import Enum

import pytest
from django.core.cache.backends.locmem import LocMemCache

from core.access import entity_scope
from core.access.entity_scope import (
    DENIED,
    EntityScope,
    grant_entity_access,
    invalidate_entity_scope,
    register_grant_loader,
    register_grant_writer,
    resolve_entity_scope,
)

pytestmark = pytest.mark.unit


class _SampleType(str, Enum):
    ITEM = 'item'


WH = _SampleType.ITEM
NORTH = uuid.uuid4()
SOUTH = uuid.uuid4()


def _user(user_id=None, role_name='Operator', authenticated=True):
    return SimpleNamespace(
        id=user_id or uuid.uuid4(), is_authenticated=authenticated, rol=SimpleNamespace(name=role_name),
    )


def _request(role_name='Operator', authenticated=True):
    return SimpleNamespace(user=_user(role_name=role_name, authenticated=authenticated))


@pytest.fixture
def cache():
    local = LocMemCache('egrant-test', {})
    with patch.object(entity_scope, 'caches', {'access': local}), \
            patch('core.cache.invalidation._cache', return_value=local), \
            patch('core.cache.invalidation.transaction.on_commit', lambda fn: fn()):
        yield local


@pytest.fixture
def loader():
    calls = []

    def load(user_id, entity_type):
        calls.append((user_id, entity_type))
        return {NORTH}

    previous = entity_scope._loader
    register_grant_loader(load)
    yield calls
    entity_scope._loader = previous


def test_admin_is_unrestricted_without_loading(cache, loader):
    scope = resolve_entity_scope(_request('Administrator'), WH)

    assert scope.unrestricted
    assert scope.ids_or_none is None
    assert scope.allows(SOUTH)
    assert loader == []


def test_user_sees_only_granted_ids(cache, loader):
    scope = resolve_entity_scope(_request(), WH)

    assert scope.ids_or_none == frozenset({NORTH})
    assert scope.allows(NORTH)
    assert not scope.allows(SOUTH)


def test_scope_is_memoized_per_request_and_cached_across_requests(cache, loader):
    request = _request()
    resolve_entity_scope(request, WH)
    resolve_entity_scope(request, WH)
    assert len(loader) == 1

    assert resolve_entity_scope(SimpleNamespace(user=request.user), WH).allows(NORTH)
    assert len(loader) == 1


def test_cache_key_is_isolated_per_tenant_schema(cache, loader):
    user = _request().user
    with patch.object(entity_scope.connection, 'schema_name', 'tenant_a', create=True):
        resolve_entity_scope(SimpleNamespace(user=user), WH)
    with patch.object(entity_scope.connection, 'schema_name', 'tenant_b', create=True):
        resolve_entity_scope(SimpleNamespace(user=user), WH)

    assert len(loader) == 2


def test_invalidation_forces_reload(cache, loader):
    request = _request()
    resolve_entity_scope(request, WH)

    invalidate_entity_scope([request.user.id], WH)
    resolve_entity_scope(SimpleNamespace(user=request.user), WH)

    assert len(loader) == 2


def test_stale_read_written_after_the_change_is_never_served(cache):
    """Lectura vieja: consulta la base antes del COMMIT y escribe en caché después."""
    user_id = uuid.uuid4()
    state = {'ids': {NORTH}}
    commit_during_load = []

    def load(_user_id, _entity_type):
        snapshot = set(state['ids'])
        for change in commit_during_load:
            change()
        return snapshot

    previous = entity_scope._loader
    register_grant_loader(load)
    try:
        def revoke():
            state['ids'] = set()
            invalidate_entity_scope([user_id], WH)

        commit_during_load.append(revoke)
        stale = resolve_entity_scope(SimpleNamespace(user=_user(user_id)), WH)
        commit_during_load.clear()
        fresh = resolve_entity_scope(SimpleNamespace(user=_user(user_id)), WH)
    finally:
        entity_scope._loader = previous

    assert stale.ids_or_none == frozenset({NORTH})
    assert fresh.ids_or_none == frozenset()


def test_evicted_version_does_not_revive_an_old_value(cache, loader):
    request = _request()
    resolve_entity_scope(request, WH)
    cache.delete(entity_scope._version_key(request.user.id, WH))

    resolve_entity_scope(SimpleNamespace(user=request.user), WH)

    assert len(loader) == 2


def test_concurrent_version_creation_keeps_the_winner(cache, loader):
    user = _request().user
    version_key = entity_scope._version_key(user.id, WH)
    with patch.object(cache, 'add', side_effect=lambda *args, **kwargs: cache.set(version_key, 'winner') and False):
        resolve_entity_scope(SimpleNamespace(user=user), WH)

    assert cache.get(entity_scope._key(user.id, WH))['v'] == 'winner'
    resolve_entity_scope(SimpleNamespace(user=user), WH)
    assert len(loader) == 1


def test_legacy_list_entry_is_reloaded(cache, loader):
    user = _request().user
    cache.set(entity_scope._key(user.id, WH), [str(SOUTH)])

    scope = resolve_entity_scope(SimpleNamespace(user=user), WH)

    assert scope.ids_or_none == frozenset({NORTH})
    assert len(loader) == 1


def test_cache_outage_falls_back_to_the_loader(loader):
    down = MagicMock()
    down.get_many.return_value = {}
    down.add.return_value = False
    down.get.return_value = None
    with patch.object(entity_scope, 'caches', {'access': down}):
        scope = resolve_entity_scope(_request(), WH)

    assert scope.ids_or_none == frozenset({NORTH})
    assert len(loader) == 1


def test_anonymous_sees_nothing(cache, loader):
    assert resolve_entity_scope(_request(authenticated=False), WH) is DENIED
    assert resolve_entity_scope(SimpleNamespace(), WH) is DENIED
    assert loader == []


def test_missing_loader_denies_and_does_not_cache(cache):
    previous = entity_scope._loader
    entity_scope._loader = None
    try:
        scope = resolve_entity_scope(_request(), WH)
    finally:
        entity_scope._loader = previous

    assert scope.ids_or_none == frozenset()


def test_grant_entity_access_delegates_to_the_registered_writer():
    calls = []
    previous = entity_scope._writer
    register_grant_writer(lambda *args: calls.append(args))
    try:
        grant_entity_access(SOUTH, WH, NORTH)
    finally:
        entity_scope._writer = previous

    assert calls == [(SOUTH, WH, NORTH, None)]


def test_grant_entity_access_without_writer_fails_loudly():
    previous = entity_scope._writer
    entity_scope._writer = None
    try:
        with pytest.raises(RuntimeError, match='writer not registered'):
            grant_entity_access(SOUTH, WH, NORTH)
    finally:
        entity_scope._writer = previous


def test_empty_scope_allows_nothing():
    assert not EntityScope(unrestricted=False).allows(NORTH)
