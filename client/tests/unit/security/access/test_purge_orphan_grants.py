"""Limpieza de accesos huérfanos: caso de uso, repositorio y comando."""
import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from client.features.security.access.entity_grants.application.use_cases import PurgeOrphanGrantsUseCase
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    OrphanPurgeSchema,
)
from client.features.security.access.entity_grants.infrastructure.repositories import (
    DjangoEntityGrantRepository,
)
from client.features.security.access.entity_grants.presentation import dependencies as deps
from client.tests.unit.security.access.grant_fakes import (
    COMPANY,
    FOREIGN_USER,
    GONE,
    NORTH,
    SOUTH,
    USER,
    FakeCatalog,
    FakeDirectory,
    FakeRepository,
)

pytestmark = pytest.mark.unit

WH = 'warehouse'
INFRA = 'client.features.security.access.entity_grants.infrastructure.repositories'
COMMAND = 'client.features.security.access.entity_grants.management.commands.purge_orphan_grants'


def _repository(*rows):
    repository = FakeRepository()
    repository.rows = {(user, WH, entity) for user, entity in rows}
    return repository


def _use_case(repository):
    catalog = FakeCatalog()
    return PurgeOrphanGrantsUseCase(repository, FakeDirectory(), lambda _type: catalog)


def _purge(use_case, repository_company, *, dry_run=False):
    return use_case._purge(repository_company, WH, dry_run)


# ── Caso de uso ──────────────────────────────────────────────────────────────


def test_purges_users_outside_the_company_and_missing_records():
    repository = _repository((USER, NORTH), (USER, GONE), (FOREIGN_USER, SOUTH))

    result = _purge(_use_case(repository), COMPANY)

    assert result.missing_users == [FOREIGN_USER]
    assert result.missing_entities == [GONE]
    assert result.deleted == 2
    assert repository.rows == {(USER, WH, NORTH)}


def test_dry_run_reports_without_deleting():
    repository = _repository((FOREIGN_USER, NORTH))

    result = _purge(_use_case(repository), COMPANY, dry_run=True)

    assert result.missing_users == [FOREIGN_USER]
    assert result.deleted == 0
    assert repository.rows == {(FOREIGN_USER, WH, NORTH)}


def test_clean_tenant_deletes_nothing():
    repository = _repository((USER, NORTH))
    repository.delete_keys = MagicMock()

    results = _use_case(repository).execute(COMPANY)

    assert all(not item.found for item in results)
    repository.delete_keys.assert_not_called()


def test_empty_tenant_skips_lookups():
    directory, catalog = FakeDirectory(), FakeCatalog()
    use_case = PurgeOrphanGrantsUseCase(FakeRepository(), directory, lambda _type: catalog)

    results = use_case.execute(COMPANY)

    assert all(not item.found for item in results)
    assert directory.calls == 0 and catalog.calls == 0


def test_purge_schema_flags_findings():
    assert not OrphanPurgeSchema(entity_type=WH, missing_users=[], missing_entities=[]).found
    assert OrphanPurgeSchema(entity_type=WH, missing_users=[USER], missing_entities=[]).found


# ── Repositorio ──────────────────────────────────────────────────────────────


@pytest.fixture
def orm():
    with patch(f'{INFRA}.EntityGrant.objects') as objects, \
            patch(f'{INFRA}.transaction') as tx, \
            patch(f'{INFRA}.advisory_xact_lock') as lock:
        yield objects, tx, lock


@pytest.mark.parametrize('axis, column', [(GrantAxis.USER, 'user_id'), (GrantAxis.ENTITY, 'entity_id')])
def test_granted_keys_reads_distinct_key_column(orm, axis, column):
    objects, _, _ = orm
    objects.filter.return_value.values_list.return_value.distinct.return_value = [NORTH]

    assert DjangoEntityGrantRepository().granted_keys(WH, axis) == {NORTH}
    objects.filter.assert_called_once_with(entity_type='warehouse')
    objects.filter.return_value.values_list.assert_called_once_with(column, flat=True)


def test_delete_keys_locks_and_deletes_in_one_statement(orm):
    objects, tx, lock = orm
    objects.filter.return_value.delete.return_value = (3, {})

    assert DjangoEntityGrantRepository().delete_keys(WH, [USER], [GONE]) == 3
    tx.atomic.assert_called_once_with()
    lock.assert_called_once_with('entity_grants', 'warehouse')
    assert objects.filter.call_args.kwargs == {'entity_type': 'warehouse'}


def test_delete_keys_without_ids_is_a_noop(orm):
    objects, tx, _ = orm

    assert DjangoEntityGrantRepository().delete_keys(WH, [], []) == 0
    tx.atomic.assert_not_called()
    objects.filter.assert_not_called()


def test_composition_root_wires_the_purge():
    use_case = deps.purge_orphan_grants()

    assert isinstance(use_case.repository, DjangoEntityGrantRepository)
    assert use_case.catalogs is deps.catalog_for


# ── Comando ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tenants():
    with patch(f'{COMMAND}.get_tenant_model') as model, patch(f'{COMMAND}.schema_context'):
        queryset = model.return_value.objects.exclude.return_value
        queryset.values_list.return_value = [(COMPANY, 'acme')]
        queryset.filter.return_value.values_list.return_value = [(COMPANY, 'acme')]
        yield queryset


def _run(results, *args):
    use_case = MagicMock()
    use_case.execute.return_value = results
    out = StringIO()
    with patch(f'{COMMAND}.deps.purge_orphan_grants', return_value=use_case):
        call_command('purge_orphan_grants', *args, stdout=out)
    return use_case, out.getvalue()


def _result(**kwargs):
    return OrphanPurgeSchema(**{'entity_type': WH, 'missing_users': [], 'missing_entities': [], **kwargs})


def test_command_purges_every_tenant(tenants):
    use_case, out = _run([_result(missing_users=[FOREIGN_USER], deleted=2)], '--all')

    use_case.execute.assert_called_once_with(COMPANY, dry_run=False)
    assert 'Tenant: acme' in out and 'deleted 2 grants (1 users, 0 records)' in out


def test_command_dry_run_on_one_schema(tenants):
    use_case, out = _run([_result(missing_entities=[GONE])], '--schema', 'acme', '--dry-run')

    tenants.filter.assert_called_once_with(schema_name='acme')
    use_case.execute.assert_called_once_with(COMPANY, dry_run=True)
    assert 'orphans for 0 users, 1 records [dry run]' in out


def test_command_reports_clean_tenants(tenants):
    _, out = _run([_result()], '--all')

    assert 'warehouse: no orphan grants' in out


def test_command_rejects_unknown_schema(tenants):
    tenants.filter.return_value.values_list.return_value = []

    with pytest.raises(CommandError, match='Unknown tenant schema'):
        _run([], '--schema', 'ghost')


def test_command_requires_a_target(tenants):
    with pytest.raises(CommandError, match='--schema'):
        _run([])
