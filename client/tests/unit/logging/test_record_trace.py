"""Trazabilidad de un registro: detalle seguro, composición, repositorio y vista."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from client.features.logging.ops.operations.application.use_cases import (
    ListRecordTraceUseCase,
    ListScopeTraceUseCase,
)
from client.features.logging.ops.operations.domain.schemas import (
    RECORD_TRACE_LIMIT,
    RELATED_REFS_KEY,
    TRACE_SCOPE_PREFIXES,
    RecordTraceEntry,
    TraceScope,
    WarehouseEventRecord,
)
from client.features.logging.ops.operations.domain.trace import build_trace_entry
from client.features.logging.ops.operations.infrastructure.actor_directory import (
    DjangoActorDirectory,
)
from client.features.logging.ops.operations.infrastructure.repositories import (
    DjangoWarehouseEventRepository,
)
from client.features.logging.ops.operations.presentation import api

pytestmark = pytest.mark.unit

_MODEL = 'client.features.logging.ops.operations.models.WarehouseEvent'
_USER_MODEL = 'client.features.logging.ops.operations.infrastructure.actor_directory.get_user_model'
_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
_REF = uuid.UUID('01a0e113-0ed6-7245-8407-f11befaa6763')
_WAREHOUSE = uuid.UUID('0199a6f4-2c1d-7c3e-9a51-6d1f0e2b8c47')


def _record(**overrides) -> WarehouseEventRecord:
    data = {'id': uuid.uuid4(), 'event_type': 'location.created', 'occurred_at': _NOW}
    data.update(overrides)
    return WarehouseEventRecord(**data)


class TestBuildTraceEntry:

    def test_keeps_codes_and_drops_ids(self):
        entry = build_trace_entry(
            _record(
                zone=' A ',
                location='A-01',
                payload={
                    'number': 'PED-10',
                    'code': 'SKU-1',
                    'sku': '11111111-1111-1111-1111-111111111111',
                    'task_id': '22222222-2222-2222-2222-222222222222',
                },
            ),
            ' Ana Ruiz ',
        )
        assert entry.detail == 'PED-10 · SKU-1'
        assert entry.actor_name == 'Ana Ruiz'
        assert entry.zone == 'A'

    def test_ignores_long_and_non_text_values(self):
        entry = build_trace_entry(_record(payload={'code': 'X' * 81, 'number': 42}))
        assert entry.detail == ''

    def test_empty_payload_has_no_detail(self):
        assert build_trace_entry(_record(payload=None)).detail == ''

    def test_entry_is_immutable(self):
        entry = build_trace_entry(_record())
        with pytest.raises(Exception):
            entry.detail = 'changed'


class TestListRecordTraceUseCase:

    def test_composes_entries_with_actor_names(self):
        actor = uuid.uuid4()
        repo = MagicMock()
        repo.list_for_reference.return_value = [
            _record(user_id=actor, payload={'code': 'UB-1'}),
            _record(user_id=None),
        ]
        actors = MagicMock()
        actors.display_names.return_value = {actor: 'Ana Ruiz'}

        result = ListRecordTraceUseCase(repo, actors).execute(_REF, 'Location')

        repo.list_for_reference.assert_called_once_with(_REF, 'Location', RECORD_TRACE_LIMIT, None)
        actors.display_names.assert_called_once_with({actor})
        assert [e.actor_name for e in result] == ['Ana Ruiz', '']
        assert result[0].detail == 'UB-1'

    def test_blank_reference_type_is_not_filtered(self):
        repo = MagicMock()
        repo.list_for_reference.return_value = []
        actors = MagicMock()
        actors.display_names.return_value = {}

        assert ListRecordTraceUseCase(repo, actors).execute(_REF, '') == []
        repo.list_for_reference.assert_called_once_with(_REF, None, RECORD_TRACE_LIMIT, None)

    def test_warehouse_widens_to_related_events(self):
        repo = MagicMock()
        repo.list_for_reference.return_value = []
        actors = MagicMock()
        actors.display_names.return_value = {}

        ListRecordTraceUseCase(repo, actors).execute(_REF, None, _WAREHOUSE)

        repo.list_for_reference.assert_called_once_with(_REF, None, RECORD_TRACE_LIMIT, _WAREHOUSE)


class TestListScopeTraceUseCase:

    def test_floor_plan_reads_only_its_events(self):
        actor = uuid.uuid4()
        repo = MagicMock()
        repo.list_for_warehouse.return_value = [_record(event_type='layout.floor_plan_uploaded', user_id=actor)]
        actors = MagicMock()
        actors.display_names.return_value = {actor: 'Ana Ruiz'}

        result = ListScopeTraceUseCase(repo, actors).execute(_WAREHOUSE, TraceScope.FLOOR_PLAN)

        repo.list_for_warehouse.assert_called_once_with(_WAREHOUSE, ('layout.floor_plan_',), RECORD_TRACE_LIMIT)
        assert result[0].actor_name == 'Ana Ruiz'

    def test_topology_covers_network_and_map_edits(self):
        repo = MagicMock()
        repo.list_for_warehouse.return_value = []
        actors = MagicMock()
        actors.display_names.return_value = {}

        assert ListScopeTraceUseCase(repo, actors).execute(_WAREHOUSE, TraceScope.TOPOLOGY) == []
        repo.list_for_warehouse.assert_called_once_with(
            _WAREHOUSE, TRACE_SCOPE_PREFIXES[TraceScope.TOPOLOGY], RECORD_TRACE_LIMIT,
        )


@pytest.mark.parametrize('event_type, scope', [
    ('layout.floor_plan_uploaded', TraceScope.FLOOR_PLAN),
    ('layout.floor_plan_calibrated', TraceScope.FLOOR_PLAN),
    ('topology.edge.created', TraceScope.TOPOLOGY),
    ('topology.version.published', TraceScope.TOPOLOGY),
    ('layout.nodes_moved', TraceScope.TOPOLOGY),
    ('layout.node_placed', TraceScope.TOPOLOGY),
    ('layout.edge_split', TraceScope.TOPOLOGY),
    ('layout.zone_outlined', TraceScope.TOPOLOGY),
    ('layout.block_created', TraceScope.TOPOLOGY),
])
def test_each_map_event_belongs_to_exactly_one_scope(event_type, scope):
    owners = [item for item, prefixes in TRACE_SCOPE_PREFIXES.items() if event_type.startswith(prefixes)]
    assert owners == [scope]


class TestRepository:

    @patch(_MODEL)
    def test_lists_newest_first_for_the_reference(self, MockEvent):
        row = SimpleNamespace(
            id=uuid.uuid4(), event_type='order.created', created_at=_NOW,
            zone=None, location='Muelle 1', payload={'number': 'PED-2'}, user_id=None,
        )
        qs = MagicMock()
        MockEvent.objects.filter.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value.only.return_value.__getitem__.return_value = [row]

        rows = DjangoWarehouseEventRepository().list_for_reference(_REF, 'Order', 10)

        MockEvent.objects.filter.assert_called_once_with(reference_id=str(_REF))
        qs.filter.assert_called_once_with(reference_type='Order')
        qs.order_by.assert_called_once_with('-created_at', '-id')
        qs.order_by.return_value.only.return_value.__getitem__.assert_called_once_with(slice(None, 10))
        assert rows[0].location == 'Muelle 1'
        assert rows[0].zone == ''
        assert rows[0].payload == {'number': 'PED-2'}

    @patch(_MODEL)
    def test_non_dict_payload_is_dropped(self, MockEvent):
        row = SimpleNamespace(
            id=uuid.uuid4(), event_type='x.y', created_at=_NOW,
            zone='', location='', payload=['legacy'], user_id=None,
        )
        qs = MockEvent.objects.filter.return_value
        qs.order_by.return_value.only.return_value.__getitem__.return_value = [row]

        rows = DjangoWarehouseEventRepository().list_for_reference(_REF, None, 5)

        qs.filter.assert_not_called()
        assert rows[0].payload is None

    @patch(_MODEL)
    def test_warehouse_adds_events_that_cite_the_record(self, MockEvent):
        qs = MockEvent.objects.filter.return_value
        qs.order_by.return_value.only.return_value.__getitem__.return_value = []

        DjangoWarehouseEventRepository().list_for_reference(_REF, 'Location', 5, _WAREHOUSE)

        (condition,), _ = MockEvent.objects.filter.call_args
        assert condition.connector == 'OR'
        own, related = condition.children
        assert sorted(own.children) == [('reference_id', str(_REF)), ('reference_type', 'Location')]
        assert sorted(related.children) == [
            ('payload__contains', {RELATED_REFS_KEY: [str(_REF)]}), ('warehouse_id', _WAREHOUSE),
        ]

    @patch(_MODEL)
    def test_lists_warehouse_events_by_prefix(self, MockEvent):
        qs = MockEvent.objects.filter.return_value
        qs.order_by.return_value.only.return_value.__getitem__.return_value = []

        DjangoWarehouseEventRepository().list_for_warehouse(_WAREHOUSE, ('topology.', 'layout.'), 7)

        (types,), kwargs = MockEvent.objects.filter.call_args
        assert kwargs == {'warehouse_id': _WAREHOUSE}
        assert types.connector == 'OR'
        assert types.children == [('event_type__startswith', 'topology.'), ('event_type__startswith', 'layout.')]
        qs.order_by.return_value.only.return_value.__getitem__.assert_called_once_with(slice(None, 7))

    @patch(_MODEL)
    def test_no_prefixes_skips_the_query(self, MockEvent):
        assert DjangoWarehouseEventRepository().list_for_warehouse(_WAREHOUSE, (), 7) == []
        MockEvent.objects.filter.assert_not_called()


class TestActorDirectory:

    @patch(_USER_MODEL)
    def test_no_ids_skips_the_query(self, get_model):
        assert DjangoActorDirectory().display_names(set()) == {}
        get_model.assert_not_called()

    @patch(_USER_MODEL)
    def test_full_name_then_username(self, get_model):
        ana, bot = uuid.uuid4(), uuid.uuid4()
        get_model.return_value.objects.filter.return_value.only.return_value = [
            SimpleNamespace(id=ana, first_name='Ana', last_name='Ruiz', username='aruiz'),
            SimpleNamespace(id=bot, first_name='', last_name=None, username=' robot '),
        ]
        assert DjangoActorDirectory().display_names({ana, bot}) == {ana: 'Ana Ruiz', bot: 'robot'}


LOCMEM_CACHES = {
    name: {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': f'{name}-trace'}
    for name in ('default', 'access', 'auth')
}


def _get(path: str):
    user_id = uuid.uuid4()
    request = APIRequestFactory().get(path)
    force_authenticate(request, user=SimpleNamespace(id=user_id, pk=user_id, is_authenticated=True))
    return api.RecordTraceView.as_view()(request)


@pytest.fixture
def member():
    with override_settings(CACHES=LOCMEM_CACHES), \
            patch.object(api.IsCompanyMember, 'has_permission', return_value=True):
        yield


@pytest.mark.parametrize('factory, use_case', [
    (api._use_case, ListRecordTraceUseCase),
    (api._scope_use_case, ListScopeTraceUseCase),
])
def test_views_compose_use_cases_over_django_adapters(factory, use_case):
    built = factory()
    assert isinstance(built, use_case)
    assert isinstance(built.repository, DjangoWarehouseEventRepository)
    assert isinstance(built.actors, DjangoActorDirectory)


@pytest.mark.usefixtures('member')
class TestRecordTraceView:

    def test_returns_items_in_english_envelope(self):
        entry = RecordTraceEntry(id=uuid.uuid4(), event_type='location.created', occurred_at=_NOW)
        with patch.object(api, '_use_case') as factory:
            factory.return_value.execute.return_value = [entry]
            response = _get(f'/record-trace/?reference_id={_REF}&reference_type=Location')

        assert response.status_code == 200
        assert response.data['message'] == 'Record trace loaded.'
        assert response.data['data']['items'][0]['event_type'] == 'location.created'
        factory.return_value.execute.assert_called_once_with(_REF, 'Location', None)

    def test_passes_the_warehouse_for_related_events(self):
        with patch.object(api, '_use_case') as factory:
            factory.return_value.execute.return_value = []
            response = _get(f'/record-trace/?reference_id={_REF}&warehouse_id={_WAREHOUSE}')

        assert response.status_code == 200
        factory.return_value.execute.assert_called_once_with(_REF, None, _WAREHOUSE)

    def test_scope_reads_the_warehouse_surface(self):
        with patch.object(api, '_scope_use_case') as factory, patch.object(api, '_use_case') as record:
            factory.return_value.execute.return_value = []
            response = _get(f'/record-trace/?scope=floor_plan&warehouse_id={_WAREHOUSE}')

        assert response.status_code == 200
        factory.return_value.execute.assert_called_once_with(_WAREHOUSE, TraceScope.FLOOR_PLAN)
        record.assert_not_called()

    def test_scope_requires_the_warehouse(self):
        with patch.object(api, '_scope_use_case') as factory:
            response = _get('/record-trace/?scope=topology')
        assert response.status_code == 400
        assert response.data['errors'][0]['field'] == 'warehouse_id'
        factory.assert_not_called()

    @pytest.mark.parametrize('extra, field', [
        (f'&reference_id={_REF}', 'reference_id'),
        ('&reference_type=Location', 'reference_type'),
    ])
    def test_scope_cannot_be_mixed_with_a_record(self, extra, field):
        with patch.object(api, '_scope_use_case') as scope, patch.object(api, '_use_case') as record:
            response = _get(f'/record-trace/?scope=topology&warehouse_id={_WAREHOUSE}{extra}')
        assert response.status_code == 400
        assert [(error['field'], error['code']) for error in response.data['errors']] == [
            (field, 'CONFLICTING_FIELD'),
        ]
        scope.assert_not_called()
        record.assert_not_called()

    def test_rejects_unknown_scope(self):
        response = _get(f'/record-trace/?scope=orders&warehouse_id={_WAREHOUSE}')
        assert response.status_code == 400

    def test_rejects_invalid_reference_id(self):
        with patch.object(api, '_use_case') as factory:
            response = _get('/record-trace/?reference_id=not-a-uuid')
        assert response.status_code == 400
        factory.assert_not_called()

    def test_requires_reference_id(self):
        assert _get('/record-trace/').status_code == 400

    def test_rejects_unsafe_reference_type(self):
        response = _get(f'/record-trace/?reference_id={_REF}&reference_type=Loc;DROP')
        assert response.status_code == 400
