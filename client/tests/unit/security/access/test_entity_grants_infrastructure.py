"""Adaptadores Django del L4 entity_grants (ORM simulado, sin DB)."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from client.features.security.access.entity_grants.apps import EntityGrantsConfig
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantScope,
)
from client.features.security.access.entity_grants.infrastructure import repositories as repo_module
from client.features.security.access.entity_grants.infrastructure.catalogs import catalog_for
from client.features.security.access.entity_grants.infrastructure.repositories import (
    DjangoEntityGrantRepository,
    load_granted_ids,
)
from client.features.security.access.entity_grants.infrastructure.scope_invalidator import (
    CacheGrantScopeInvalidator,
)
from client.features.security.access.entity_grants.infrastructure.user_directory import (
    DjangoCompanyUserDirectory,
)
from client.features.security.access.entity_grants.models import EntityGrant

pytestmark = pytest.mark.unit

INFRA = 'client.features.security.access.entity_grants.infrastructure'
WH = 'warehouse'
USER = uuid.uuid4()
GRANTOR = uuid.uuid4()
A, B, C = (uuid.UUID(f'0000000{i}-0000-7000-8000-000000000000') for i in (1, 2, 3))


@pytest.fixture
def orm():
    with patch(f'{INFRA}.repositories.EntityGrant.objects') as objects, \
            patch(f'{INFRA}.repositories.transaction') as tx, \
            patch(f'{INFRA}.repositories.advisory_xact_lock') as lock:
        yield objects, tx, lock


def _scope(axis=GrantAxis.USER, key=USER):
    return GrantScope(entity_type=WH, axis=axis, key_id=key)


@pytest.mark.parametrize('axis, key_col, value_col', [
    (GrantAxis.USER, 'user_id', 'entity_id'),
    (GrantAxis.ENTITY, 'entity_id', 'user_id'),
])
def test_list_ids_reads_only_the_value_column(orm, axis, key_col, value_col):
    objects, _, _ = orm
    objects.filter.return_value.values_list.return_value = [A]

    assert DjangoEntityGrantRepository().list_ids(_scope(axis)) == {A}

    objects.filter.assert_called_once_with(entity_type='warehouse', **{key_col: USER})
    objects.filter.return_value.values_list.assert_called_once_with(value_col, flat=True)


def test_replace_locks_then_writes_only_the_difference(orm):
    objects, tx, lock = orm
    objects.filter.return_value.values_list.return_value = [A, B]

    diff = DjangoEntityGrantRepository().replace(_scope(), [B, C], GRANTOR)

    tx.atomic.assert_called_once_with()
    lock.assert_called_once_with('entity_grants', 'warehouse')
    assert diff.added == [C] and diff.removed == [A]
    objects.filter.assert_any_call(entity_type='warehouse', user_id=USER, entity_id__in=[A])
    objects.filter.return_value.delete.assert_called_once_with()
    created = objects.bulk_create.call_args.args[0]
    assert [(row.user_id, row.entity_id, row.granted_by) for row in created] == [(USER, C, GRANTOR)]
    assert isinstance(created[0], EntityGrant)


def test_replace_from_entity_writes_user_rows(orm):
    objects, _, _ = orm
    objects.filter.return_value.values_list.return_value = []

    diff = DjangoEntityGrantRepository().replace(_scope(GrantAxis.ENTITY, A), [USER], None)

    assert diff.added == [USER]
    created = objects.bulk_create.call_args.args[0]
    assert (created[0].user_id, created[0].entity_id) == (USER, A)
    objects.filter.return_value.delete.assert_not_called()


def test_replace_without_changes_writes_nothing(orm):
    objects, _, _ = orm
    objects.filter.return_value.values_list.return_value = [A]

    diff = DjangoEntityGrantRepository().replace(_scope(), [A], GRANTOR)

    assert not diff.changed
    objects.bulk_create.assert_not_called()
    objects.filter.return_value.delete.assert_not_called()


def test_loader_reads_the_user_axis(orm):
    objects, _, _ = orm
    objects.filter.return_value.values_list.return_value = [A]

    assert load_granted_ids(USER, WH) == {A}
    objects.filter.assert_called_once_with(entity_type='warehouse', user_id=USER)


def test_catalog_for_unknown_type_is_not_registered():
    from core.errors import NotFoundException

    with pytest.raises(NotFoundException):
        catalog_for(WH)


def test_user_directory_filters_by_company():
    company = uuid.uuid4()
    with patch(f'{INFRA}.user_directory.User.objects') as objects:
        objects.filter.return_value.values_list.return_value = [USER]
        assert DjangoCompanyUserDirectory().member_ids(company, [USER, A]) == {USER}
    objects.filter.assert_called_once_with(company_id=company, id__in=[USER, A])


def test_invalidator_delegates_to_core_scope():
    with patch(f'{INFRA}.scope_invalidator.invalidate_entity_scope') as invalidate:
        CacheGrantScopeInvalidator().invalidate([USER], WH)
    invalidate.assert_called_once_with([USER], WH)


def test_app_registers_the_loader_and_writer_in_core():
    config = MagicMock(spec=EntityGrantsConfig)
    with patch('core.access.entity_scope.register_grant_loader') as loader, \
            patch('core.access.entity_scope.register_grant_writer') as writer:
        EntityGrantsConfig.ready(config)
    loader.assert_called_once_with(repo_module.load_granted_ids)
    writer.assert_called_once_with(repo_module.grant_entity)


def test_writer_inserts_idempotently_and_refreshes_the_user_scope(orm):
    objects, _, _ = orm
    with patch(f'{INFRA}.repositories.invalidate_entity_scope') as invalidate:
        repo_module.grant_entity(USER, WH, A, GRANTOR)

    [row] = objects.bulk_create.call_args.args[0]
    assert (row.user_id, row.entity_type, row.entity_id, row.granted_by) == (USER, 'warehouse', A, GRANTOR)
    assert objects.bulk_create.call_args.kwargs == {'ignore_conflicts': True}
    invalidate.assert_called_once_with([USER], WH)


def test_composition_root_rejects_unregistered_types():
    from core.errors import NotFoundException
    from client.features.security.access.entity_grants.presentation import dependencies as deps

    with pytest.raises(NotFoundException):
        deps.get_grant_set(WH)
    with pytest.raises(NotFoundException):
        deps.replace_grant_set(WH)


@pytest.mark.parametrize('path, view_name', [
    (f'/api/v1/access/entity-grants/users/{USER}/', 'UserGrantSetView'),
    (f'/api/v1/access/entity-grants/entities/{A}/', 'EntityGrantSetView'),
])
def test_routes_resolve_to_grant_views(path, view_name):
    from django.urls import resolve

    match = resolve(path)
    assert match.func.view_class.__name__ == view_name
    assert isinstance(match.kwargs['key_id'], uuid.UUID)


def test_model_str_names_the_grant():
    grant = EntityGrant(user_id=USER, entity_type='warehouse', entity_id=A)
    assert str(grant) == f'warehouse:{A} · user={USER}'
