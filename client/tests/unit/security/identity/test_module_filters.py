import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from client.features.security.identity.module_filters.application.use_cases import (
    ActivateModuleFilterUseCase,
    CreateModuleFilterUseCase,
    DeactivateModuleFiltersUseCase,
    DeleteModuleFilterUseCase,
    ListModuleFiltersUseCase,
    UpdateModuleFilterUseCase,
)
from client.features.security.identity.module_filters.domain.interfaces import (
    IFacilityCatalog,
    IModuleFilterRepository,
)
from client.features.security.identity.module_filters.domain.schemas import (
    MAX_FILTERS_PER_MODULE,
    FacilityLabels,
    FilterCriteria,
    ModuleFilterInput,
    ModuleFilterPatch,
    ModuleFilterRecord,
    ModuleKey,
)
from client.features.security.identity.module_filters.presentation.bodies import (
    CreateModuleFilterBody,
    DeactivateModuleFiltersBody,
    UpdateModuleFilterBody,
)

pytestmark = pytest.mark.unit

USER = uuid.uuid4()
OTHER_USER = uuid.uuid4()
WAREHOUSE = uuid.uuid4()
OTHER_WAREHOUSE = uuid.uuid4()
ZONE_A = uuid.uuid4()
ZONE_B = uuid.uuid4()
FOREIGN_ZONE = uuid.uuid4()


class FakeRepository(IModuleFilterRepository):
    def __init__(self):
        self.rows: dict[uuid.UUID, tuple[uuid.UUID, ModuleFilterRecord]] = {}

    def _put(self, owner, record):
        self.rows[record.id] = (owner, record)
        return record

    def _owned(self, user_id, module_key=None):
        return [
            rec for owner, rec in self.rows.values()
            if owner == user_id and (module_key is None or rec.module_key == module_key)
        ]

    def list_for_user(self, user_id, module_key):
        return sorted(self._owned(user_id, module_key), key=lambda r: r.name)

    def get(self, user_id, filter_id):
        owner, rec = self.rows.get(filter_id, (None, None))
        return rec if owner == user_id else None

    def count_for_user(self, user_id, module_key):
        return len(self._owned(user_id, module_key))

    def name_taken(self, user_id, module_key, name, exclude_id=None):
        return any(
            r.name.lower() == name.lower() and r.id != exclude_id
            for r in self._owned(user_id, module_key)
        )

    def create(self, user_id, data):
        if data.activate:
            self.deactivate_all(user_id, data.module_key)
        now = datetime.now(timezone.utc)
        return self._put(user_id, ModuleFilterRecord(
            id=uuid.uuid4(), module_key=data.module_key, name=data.name,
            criteria=data.criteria, is_active=data.activate, created_at=now, updated_at=now,
        ))

    def update(self, user_id, filter_id, name, criteria):
        rec = self.get(user_id, filter_id)
        changes = {k: v for k, v in {'name': name, 'criteria': criteria}.items() if v is not None}
        return self._put(user_id, rec.model_copy(update=changes))

    def delete(self, user_id, filter_id):
        self.rows.pop(filter_id, None)

    def activate(self, user_id, filter_id):
        rec = self.get(user_id, filter_id)
        self.deactivate_all(user_id, rec.module_key)
        return self._put(user_id, rec.model_copy(update={'is_active': True}))

    def deactivate_all(self, user_id, module_key):
        changed = 0
        for rec in self._owned(user_id, module_key):
            if rec.is_active:
                self._put(user_id, rec.model_copy(update={'is_active': False}))
                changed += 1
        return changed


class FakeCatalog(IFacilityCatalog):
    def __init__(self):
        self.active = {WAREHOUSE: 'Bodega Norte'}
        self.zones = {ZONE_A: (WAREHOUSE, 'Picking'), ZONE_B: (WAREHOUSE, 'Reserva'),
                      FOREIGN_ZONE: (OTHER_WAREHOUSE, 'Ajena')}

    def active_warehouse_exists(self, warehouse_id):
        return warehouse_id in self.active

    def zones_in_warehouse(self, warehouse_id, zone_ids):
        return {z for z in zone_ids if self.zones.get(z, (None,))[0] == warehouse_id}

    def labels(self, warehouse_ids, zone_ids):
        return FacilityLabels(
            warehouses={w: n for w, n in self.active.items() if w in warehouse_ids},
            zones={z: v[1] for z, v in self.zones.items() if z in zone_ids},
        )


def _input(name='Norte', zones=None, activate=False, warehouse=WAREHOUSE):
    return ModuleFilterInput(
        module_key=ModuleKey.WAREHOUSE,
        name=name,
        criteria=FilterCriteria(warehouse_id=warehouse, zone_ids=zones or []),
        activate=activate,
    )


@pytest.fixture
def repo():
    return FakeRepository()


@pytest.fixture
def catalog():
    return FakeCatalog()


# ── Happy paths ──────────────────────────────────────────────────────────────

def test_create_enriches_names_and_activates(repo, catalog):
    result = CreateModuleFilterUseCase(repo, catalog).execute(
        USER, _input(zones=[ZONE_A, ZONE_B, ZONE_A], activate=True),
    )
    assert result.is_active
    assert result.warehouse_name == 'Bodega Norte'
    assert result.zone_names == ['Picking', 'Reserva']
    assert result.criteria.zone_ids == [ZONE_A, ZONE_B]
    assert result.available


def test_only_one_active_per_module(repo, catalog):
    create = CreateModuleFilterUseCase(repo, catalog)
    first = create.execute(USER, _input('A', activate=True))
    second = create.execute(USER, _input('B'))
    ActivateModuleFilterUseCase(repo, catalog).execute(USER, second.id)

    listing = ListModuleFiltersUseCase(repo, catalog).execute(USER, ModuleKey.WAREHOUSE)
    assert listing.active_id == second.id
    assert [item.is_active for item in listing.items] == [False, True]
    assert repo.get(USER, first.id).is_active is False


def test_deactivate_all_leaves_no_active(repo, catalog):
    CreateModuleFilterUseCase(repo, catalog).execute(USER, _input(activate=True))
    DeactivateModuleFiltersUseCase(repo).execute(USER, ModuleKey.WAREHOUSE)
    listing = ListModuleFiltersUseCase(repo, catalog).execute(USER, ModuleKey.WAREHOUSE)
    assert listing.active_id is None


def test_update_and_delete(repo, catalog):
    created = CreateModuleFilterUseCase(repo, catalog).execute(USER, _input())
    updated = UpdateModuleFilterUseCase(repo, catalog).execute(
        USER, created.id, ModuleFilterPatch(name='  Norte   picking ', criteria=FilterCriteria(
            warehouse_id=WAREHOUSE, zone_ids=[ZONE_A],
        )),
    )
    assert updated.name == 'Norte picking'
    assert updated.zone_names == ['Picking']
    DeleteModuleFilterUseCase(repo).execute(USER, created.id)
    assert repo.get(USER, created.id) is None


def test_listing_marks_unavailable_warehouse(repo, catalog):
    created = CreateModuleFilterUseCase(repo, catalog).execute(USER, _input(activate=True))
    catalog.active.pop(WAREHOUSE)
    listing = ListModuleFiltersUseCase(repo, catalog).execute(USER, ModuleKey.WAREHOUSE)
    assert listing.items[0].id == created.id
    assert listing.items[0].available is False
    assert listing.items[0].warehouse_name is None


# ── Failure paths ────────────────────────────────────────────────────────────

def test_create_rejects_inactive_warehouse(repo, catalog):
    with pytest.raises(ValidationAppException) as exc:
        CreateModuleFilterUseCase(repo, catalog).execute(USER, _input(warehouse=OTHER_WAREHOUSE))
    assert exc.value.code == AppErrorCode.MFLT_WAREHOUSE_UNAVAILABLE


def test_create_rejects_zone_from_other_warehouse(repo, catalog):
    with pytest.raises(ValidationAppException) as exc:
        CreateModuleFilterUseCase(repo, catalog).execute(USER, _input(zones=[ZONE_A, FOREIGN_ZONE]))
    assert exc.value.code == AppErrorCode.MFLT_ZONE_OUTSIDE_WAREHOUSE
    assert exc.value.context['zone_ids'] == [str(FOREIGN_ZONE)]


def test_create_rejects_duplicate_name_case_insensitive(repo, catalog):
    create = CreateModuleFilterUseCase(repo, catalog)
    create.execute(USER, _input('Norte'))
    with pytest.raises(ConflictException) as exc:
        create.execute(USER, _input('norte'))
    assert exc.value.code == AppErrorCode.MFLT_DUPLICATE_NAME


def test_create_enforces_limit(repo, catalog):
    create = CreateModuleFilterUseCase(repo, catalog)
    for index in range(MAX_FILTERS_PER_MODULE):
        create.execute(USER, _input(f'F{index}'))
    with pytest.raises(ConflictException) as exc:
        create.execute(USER, _input('extra'))
    assert exc.value.code == AppErrorCode.MFLT_LIMIT_REACHED


def test_other_user_filter_is_not_found(repo, catalog):
    created = CreateModuleFilterUseCase(repo, catalog).execute(OTHER_USER, _input())
    for action in (
        lambda: ActivateModuleFilterUseCase(repo, catalog).execute(USER, created.id),
        lambda: DeleteModuleFilterUseCase(repo).execute(USER, created.id),
        lambda: UpdateModuleFilterUseCase(repo, catalog).execute(
            USER, created.id, ModuleFilterPatch(name='x'),
        ),
    ):
        with pytest.raises(NotFoundException) as exc:
            action()
        assert exc.value.code == AppErrorCode.MFLT_NOT_FOUND


def test_activate_rejects_filter_with_retired_warehouse(repo, catalog):
    created = CreateModuleFilterUseCase(repo, catalog).execute(USER, _input())
    catalog.active.pop(WAREHOUSE)
    with pytest.raises(ValidationAppException) as exc:
        ActivateModuleFilterUseCase(repo, catalog).execute(USER, created.id)
    assert exc.value.code == AppErrorCode.MFLT_WAREHOUSE_UNAVAILABLE


def test_schema_rejects_blank_name():
    with pytest.raises(ValidationError):
        _input(name='   ')


# ── Presentation bodies ──────────────────────────────────────────────────────

def _valid_body(**overrides):
    payload = {
        'module_key': 'warehouse',
        'name': 'Norte',
        'criteria': {'warehouse_id': str(WAREHOUSE), 'zone_ids': [str(ZONE_A)]},
    }
    payload.update(overrides)
    return payload


def test_create_body_accepts_valid_payload():
    body = CreateModuleFilterBody(_valid_body(activate=True))
    ok, errors = body.validate()
    assert ok, errors
    ModuleFilterInput(**body.validated_data)


@pytest.mark.parametrize('overrides', [
    {'module_key': 'orders'},
    {'name': ''},
    {'name': 'x' * 81},
    {'criteria': {'warehouse_id': 'not-a-uuid'}},
    {'criteria': {'warehouse_id': str(WAREHOUSE), 'zone_ids': ['bad']}},
    {'criteria': {'warehouse_id': str(WAREHOUSE), 'zone_ids': [str(uuid.uuid4()) for _ in range(51)]}},
    {'criteria': {'warehouse_id': str(WAREHOUSE), 'extra': 1}},
    {'unexpected': True},
])
def test_create_body_rejects_invalid_payload(overrides):
    ok, _ = CreateModuleFilterBody(_valid_body(**overrides)).validate()
    assert not ok


def test_update_rejects_duplicate_name_and_foreign_zone(repo, catalog):
    create = CreateModuleFilterUseCase(repo, catalog)
    create.execute(USER, _input('Norte'))
    other = create.execute(USER, _input('Sur'))
    update = UpdateModuleFilterUseCase(repo, catalog)
    with pytest.raises(ConflictException) as duplicate:
        update.execute(USER, other.id, ModuleFilterPatch(name='norte'))
    assert duplicate.value.code == AppErrorCode.MFLT_DUPLICATE_NAME
    with pytest.raises(ValidationAppException) as foreign:
        update.execute(USER, other.id, ModuleFilterPatch(
            criteria=FilterCriteria(warehouse_id=WAREHOUSE, zone_ids=[FOREIGN_ZONE]),
        ))
    assert foreign.value.code == AppErrorCode.MFLT_ZONE_OUTSIDE_WAREHOUSE


def test_list_is_scoped_to_the_user_and_deactivate_counts(repo, catalog):
    CreateModuleFilterUseCase(repo, catalog).execute(OTHER_USER, _input(activate=True))
    CreateModuleFilterUseCase(repo, catalog).execute(USER, _input('Mine', activate=True))
    listing = ListModuleFiltersUseCase(repo, catalog).execute(USER, ModuleKey.WAREHOUSE)
    assert [item.name for item in listing.items] == ['Mine']
    assert DeactivateModuleFiltersUseCase(repo).execute(USER, ModuleKey.WAREHOUSE) == 1
    assert ListModuleFiltersUseCase(repo, catalog).execute(USER, ModuleKey.WAREHOUSE).active_id is None


def test_list_query_requires_a_known_module_key():
    from client.features.security.identity.module_filters.presentation.queries import (
        ModuleFilterListQuery,
    )

    ok, errors = ModuleFilterListQuery({}).validate()
    assert not ok
    assert any(err.field == 'module_key' for err in errors)
    ok, errors = ModuleFilterListQuery({'module_key': 'orders'}).validate()
    assert not ok
    ok, errors = ModuleFilterListQuery({'module_key': 'warehouse'}).validate()
    assert ok, errors


def test_writes_lock_the_user_and_module_scope():
    from unittest.mock import patch

    from client.features.security.identity.module_filters.infrastructure import repositories

    with patch.object(repositories, 'advisory_xact_lock') as lock:
        repositories._lock_scope(USER, ModuleKey.WAREHOUSE.value)

    lock.assert_called_once_with('module_filters', USER, ModuleKey.WAREHOUSE.value)


def test_name_integrity_error_maps_only_the_name_constraint():
    from django.db import IntegrityError

    from client.features.security.identity.module_filters.infrastructure.repositories import (
        name_conflict_or_none,
    )

    conflict = name_conflict_or_none(
        IntegrityError(
            'duplicate key value violates unique constraint "mflt_user_module_name_ci"',
        ),
        'Norte',
    )
    assert conflict is not None
    assert conflict.code == AppErrorCode.MFLT_DUPLICATE_NAME
    assert name_conflict_or_none(
        IntegrityError('duplicate key value violates unique constraint "mflt_user_module_active_uniq"'),
        'Norte',
    ) is None


def test_update_and_deactivate_bodies():
    ok, errors = UpdateModuleFilterBody({'name': 'Sur'}).validate()
    assert ok, errors
    ok, _ = UpdateModuleFilterBody({'is_active': True}).validate()
    assert not ok
    ok, _ = DeactivateModuleFiltersBody({}).validate()
    assert not ok
    ok, errors = DeactivateModuleFiltersBody({'module_key': 'warehouse'}).validate()
    assert ok, errors


def test_legacy_location_module_key_coerces_to_warehouse():
    from client.features.security.identity.module_filters.infrastructure.repositories import (
        _coerce_module_key,
        _stored_module_keys,
    )

    assert _coerce_module_key('location') is ModuleKey.WAREHOUSE
    assert _coerce_module_key('warehouse') is ModuleKey.WAREHOUSE
    assert _stored_module_keys(ModuleKey.WAREHOUSE) == ('warehouse', 'location')
