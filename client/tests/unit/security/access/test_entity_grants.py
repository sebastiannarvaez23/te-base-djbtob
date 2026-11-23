"""Use cases, schemas y validadores de entrada del L4 entity_grants."""
import uuid

import pytest
from pydantic import ValidationError

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from client.features.security.access.entity_grants.application.use_cases import (
    GetGrantSetUseCase,
    ReplaceGrantSetUseCase,
)
from client.features.security.access.entity_grants.domain.schemas import (
    MAX_GRANTS_PER_REQUEST,
    GrantAxis,
    GrantDiff,
    GrantScope,
    GrantSetInput,
)
from client.features.security.access.entity_grants.presentation.bodies import ReplaceGrantSetBody
from client.features.security.access.entity_grants.presentation.queries import GrantSetQuery
from client.tests.unit.security.access.grant_fakes import (
    ADMIN,
    COMPANY,
    FOREIGN_USER,
    GONE,
    NORTH,
    OTHER_USER,
    SOUTH,
    USER,
    FakeCatalog,
    FakeDirectory,
    FakeRepository,
    SpyInvalidator,
)

pytestmark = pytest.mark.unit

WH = 'warehouse'


def _user(key=USER):
    return GrantScope(entity_type=WH, axis=GrantAxis.USER, key_id=key)


def _entity(key=NORTH):
    return GrantScope(entity_type=WH, axis=GrantAxis.ENTITY, key_id=key)


@pytest.fixture
def env():
    class Env:
        repo = FakeRepository()
        directory = FakeDirectory()
        catalog = FakeCatalog()
        spy = SpyInvalidator()

        def replace(self, scope, ids):
            return ReplaceGrantSetUseCase(self.repo, self.directory, self.catalog, self.spy).execute(
                COMPANY, scope, GrantSetInput(ids=ids), ADMIN,
            )

        def get(self, scope):
            return GetGrantSetUseCase(self.repo, self.directory, self.catalog).execute(COMPANY, scope)

    return Env()


# ── Desde el usuario ──────────────────────────────────────────────────────

def test_replace_from_user_sets_exactly_the_requested_warehouses(env):
    env.replace(_user(), [NORTH])

    result = env.replace(_user(), [SOUTH])

    assert result.ids == [SOUTH]
    assert result.added == [SOUTH] and result.removed == [NORTH]
    assert env.get(_user()).ids == [SOUTH]
    assert env.spy.calls[-1] == ({USER}, WH)


def test_replace_from_user_with_empty_list_revokes_all_without_catalog_query(env):
    env.replace(_user(), [NORTH])
    env.catalog.calls = 0

    result = env.replace(_user(), [])

    assert result.removed == [NORTH]
    assert env.get(_user()).ids == []
    assert env.catalog.calls == 0


def test_replace_without_changes_skips_invalidation(env):
    env.replace(_user(), [NORTH])
    env.spy.calls.clear()

    result = env.replace(_user(), [NORTH])

    assert not result.changed
    assert env.spy.calls == []


def test_replace_from_user_rejects_removed_warehouse(env):
    with pytest.raises(ValidationAppException) as caught:
        env.replace(_user(), [NORTH, GONE])

    assert caught.value.code == AppErrorCode.GRANT_ENTITY_UNAVAILABLE
    assert caught.value.context['ids'] == [str(GONE)]
    assert env.repo.rows == set()
    assert env.spy.calls == []


@pytest.mark.parametrize('action', ['get', 'replace'])
def test_user_from_another_company_is_not_found(env, action):
    with pytest.raises(NotFoundException) as caught:
        if action == 'get':
            env.get(_user(FOREIGN_USER))
        else:
            env.replace(_user(FOREIGN_USER), [NORTH])

    assert caught.value.code == AppErrorCode.USER_NOT_FOUND


# ── Desde la entidad ──────────────────────────────────────────────────────

def test_replace_from_entity_invalidates_added_and_removed_users(env):
    env.replace(_entity(), [USER])

    result = env.replace(_entity(), [OTHER_USER])

    assert result.ids == [OTHER_USER]
    assert env.get(_entity()).ids == [OTHER_USER]
    assert env.spy.calls[-1] == ({USER, OTHER_USER}, WH)


def test_both_axes_share_the_same_grants(env):
    env.replace(_entity(NORTH), [USER])
    env.replace(_entity(SOUTH), [USER])

    assert set(env.get(_user()).ids) == {NORTH, SOUTH}


def test_replace_from_entity_rejects_users_outside_company(env):
    with pytest.raises(ValidationAppException) as caught:
        env.replace(_entity(), [USER, FOREIGN_USER])

    assert caught.value.code == AppErrorCode.GRANT_USER_OUTSIDE_COMPANY
    assert caught.value.context['ids'] == [str(FOREIGN_USER)]
    assert env.repo.rows == set()


@pytest.mark.parametrize('action', ['get', 'replace'])
def test_missing_warehouse_is_not_found(env, action):
    with pytest.raises(NotFoundException) as caught:
        if action == 'get':
            env.get(_entity(GONE))
        else:
            env.replace(_entity(GONE), [USER])

    assert caught.value.code == AppErrorCode.GRANT_ENTITY_NOT_FOUND


# ── Schemas ───────────────────────────────────────────────────────────────

def test_input_dedupes_keeping_order():
    assert GrantSetInput(ids=[SOUTH, NORTH, SOUTH]).ids == [SOUTH, NORTH]


def test_input_caps_ids():
    with pytest.raises(ValidationError):
        GrantSetInput(ids=[uuid.uuid4() for _ in range(MAX_GRANTS_PER_REQUEST + 1)])


def test_input_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        GrantSetInput(ids=[], extra=True)


def test_scope_is_immutable():
    scope = _user()
    with pytest.raises(ValidationError):
        scope.key_id = NORTH


def test_diff_changed():
    assert not GrantDiff().changed
    assert GrantDiff(removed=[NORTH]).changed


# ── Body / query ──────────────────────────────────────────────────────────

def test_body_rejects_when_no_entity_types_are_registered():
    ok, errors = ReplaceGrantSetBody({'entity_type': 'warehouse', 'ids': []}).validate()
    assert not ok
    assert any(error.field.startswith('entity_type') for error in errors)


@pytest.mark.parametrize('payload', [
    {'entity_type': 'planet', 'ids': []},
    {'entity_type': 'warehouse', 'ids': ['nope']},
    {'entity_type': 'warehouse'},
    {'entity_type': 'warehouse', 'ids': [], 'extra': 1},
    {'entity_type': 'warehouse', 'ids': [str(uuid.uuid4())] * (MAX_GRANTS_PER_REQUEST + 1)},
])
def test_body_rejects_invalid_input(payload):
    ok, _ = ReplaceGrantSetBody(payload).validate()
    assert not ok


def test_query_requires_entity_type():
    ok, errors = GrantSetQuery({}).validate()
    assert not ok
    assert errors[-1].field == 'entity_type'


def test_query_rejects_unregistered_entity_type():
    ok, _ = GrantSetQuery({'entity_type': 'warehouse'}).validate()
    assert not ok
