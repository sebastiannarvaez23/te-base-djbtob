"""Actividad reciente: hitos de piso, sin eventos de línea ni reintentos."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from pydantic import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from client.features.logging.ops.operations.application.use_cases import ListRecentActivityUseCase
from client.features.logging.ops.operations.domain.activity import (
    activity_count,
    build_activity_entry,
    dedupe_milestones,
    is_milestone,
)
from client.features.logging.ops.operations.domain.schemas import (
    RECENT_ACTIVITY_EVENT_TYPES,
    RECENT_ACTIVITY_LIMIT,
    RecentActivityEntry,
    WarehouseEventRecord,
)
from client.features.logging.ops.operations.infrastructure.repositories import (
    DjangoWarehouseEventRepository,
)
from client.features.logging.ops.operations.presentation import api

pytestmark = pytest.mark.unit

_MODEL = 'client.features.logging.ops.operations.models.WarehouseEvent'
_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
_FETCH = RECENT_ACTIVITY_LIMIT * ListRecentActivityUseCase.OVERFETCH


def _record(**overrides) -> WarehouseEventRecord:
    data = {'id': uuid.uuid4(), 'event_type': 'dispatches.exited', 'occurred_at': _NOW}
    data.update(overrides)
    return WarehouseEventRecord(**data)


def _entry(**overrides) -> RecentActivityEntry:
    data = {'id': uuid.uuid4(), 'event_type': 'dispatches.exited', 'occurred_at': _NOW}
    data.update(overrides)
    return RecentActivityEntry(**data)


class TestBuildActivityEntry:

    def test_keeps_document_code_and_count(self):
        entry = build_activity_entry(_record(
            payload={
                'number': 'DSP-1042',
                'task_count': 12,
                'order_id': '11111111-1111-1111-1111-111111111111',
            },
            reference_type=' Dispatch ',
            reference_id=' ref-1 ',
        ))
        assert entry.detail == 'DSP-1042'
        assert entry.count == 12
        assert entry.reference_type == 'Dispatch'
        assert entry.reference_id == 'ref-1'

    def test_drops_uuid_codes_and_bool_counts(self):
        entry = build_activity_entry(_record(payload={
            'number': '11111111-1111-1111-1111-111111111111',
            'task_count': True,
            'lines_count': 14,
        }))
        assert entry.detail == ''
        assert entry.count == 14

    def test_empty_payload_has_no_detail(self):
        entry = build_activity_entry(_record(payload=None))
        assert entry.detail == ''
        assert entry.count is None

    def test_rejects_non_milestone_type(self):
        with pytest.raises(ValidationError):
            build_activity_entry(_record(event_type='receiving.line_received'))


class TestActivityCount:

    @pytest.mark.parametrize('payload, expected', [
        (None, None),
        ({}, None),
        ({'task_count': -1}, None),
        ({'task_count': 10_001}, None),
        ({'task_count': '3'}, None),
        ({'task_count': 0}, 0),
        ({'lines_count': 7}, 7),
    ])
    def test_only_bounded_integers(self, payload, expected):
        assert activity_count(payload) == expected


class TestIsMilestone:

    def test_milestone_type(self):
        assert is_milestone(_record(payload={'number': 'DSP-1'}))

    def test_line_event_is_not_a_milestone(self):
        assert not is_milestone(_record(event_type='packing.line_verified'))

    def test_idempotent_replay_is_not_a_milestone(self):
        assert not is_milestone(_record(payload={'replayed': True}))

    def test_replayed_false_is_a_milestone(self):
        assert is_milestone(_record(payload={'replayed': False}))


class TestDedupeMilestones:

    def test_keeps_newest_of_same_document_and_detail(self):
        newest = _entry(reference_id='t-1', detail='PKG-0001-02')
        replay = _entry(reference_id='t-1', detail='PKG-0001-02')
        other_box = _entry(reference_id='t-1', detail='PKG-0001-01')
        assert dedupe_milestones([newest, replay, other_box]) == [newest, other_box]

    def test_entries_without_reference_are_never_merged(self):
        first = _entry(reference_id='')
        second = _entry(reference_id='')
        assert dedupe_milestones([first, second]) == [first, second]


class TestListRecentActivityUseCase:

    def test_maps_milestones_with_overfetch(self):
        repo = MagicMock()
        repo.list_recent.return_value = [_record(payload={'number': 'DSP-1'})]

        result = ListRecentActivityUseCase(repo).execute(5)

        repo.list_recent.assert_called_once_with(
            RECENT_ACTIVITY_EVENT_TYPES, 5 * ListRecentActivityUseCase.OVERFETCH,
        )
        assert result[0].detail == 'DSP-1'
        assert result[0].event_type == 'dispatches.exited'

    def test_empty_feed(self):
        repo = MagicMock()
        repo.list_recent.return_value = []
        assert ListRecentActivityUseCase(repo).execute() == []
        repo.list_recent.assert_called_once_with(RECENT_ACTIVITY_EVENT_TYPES, _FETCH)

    def test_drops_line_events_and_replays(self):
        repo = MagicMock()
        repo.list_recent.return_value = [
            _record(event_type='receiving.line_received', payload={'number': 'RCV-1'}),
            _record(event_type='packing.line_verified'),
            _record(payload={'replayed': True, 'number': 'DSP-9'}),
            _record(event_type='packing.package_closed', payload={'number': 'PKG-9'}),
        ]
        result = ListRecentActivityUseCase(repo).execute()
        assert [item.event_type for item in result] == ['packing.package_closed']

    def test_trims_to_requested_limit_after_dedupe(self):
        repo = MagicMock()
        repo.list_recent.return_value = [
            _record(payload={'number': f'DSP-{i}'}, reference_id=f'd-{i}') for i in range(6)
        ]
        assert len(ListRecentActivityUseCase(repo).execute(3)) == 3

    def test_out_of_range_limit_uses_the_cap(self):
        repo = MagicMock()
        repo.list_recent.return_value = []
        ListRecentActivityUseCase(repo).execute(0)
        repo.list_recent.assert_called_once_with(RECENT_ACTIVITY_EVENT_TYPES, _FETCH)


class TestRepository:

    @patch(_MODEL)
    def test_lists_milestones_without_replays_newest_first(self, MockEvent):
        row = SimpleNamespace(
            id=uuid.uuid4(),
            event_type='picking.tasks_created',
            created_at=_NOW,
            payload={'task_count': 3},
            reference_type='Order',
            reference_id='ord-1',
        )
        filtered = MockEvent.objects.filter.return_value
        ordered = filtered.exclude.return_value.order_by.return_value
        ordered.only.return_value.__getitem__.return_value = [row]

        rows = DjangoWarehouseEventRepository().list_recent(RECENT_ACTIVITY_EVENT_TYPES, 15)

        MockEvent.objects.filter.assert_called_once_with(
            event_type__in=list(RECENT_ACTIVITY_EVENT_TYPES),
        )
        filtered.exclude.assert_called_once_with(payload__replayed=True)
        filtered.exclude.return_value.order_by.assert_called_once_with('-created_at', '-id')
        ordered.only.return_value.__getitem__.assert_called_once_with(slice(None, 15))
        assert rows[0].event_type == 'picking.tasks_created'
        assert rows[0].payload == {'task_count': 3}
        assert rows[0].reference_id == 'ord-1'

    @patch(_MODEL)
    def test_null_reference_and_non_dict_payload(self, MockEvent):
        row = SimpleNamespace(
            id=uuid.uuid4(), event_type='returns.closed', created_at=_NOW,
            payload=['legacy'], reference_type=None, reference_id=None,
        )
        chain = MockEvent.objects.filter.return_value.exclude.return_value.order_by.return_value
        chain.only.return_value.__getitem__.return_value = [row]

        rows = DjangoWarehouseEventRepository().list_recent(RECENT_ACTIVITY_EVENT_TYPES, 5)

        assert rows[0].payload is None
        assert rows[0].reference_type == ''
        assert rows[0].reference_id == ''


def test_view_factory_wires_the_django_repository():
    use_case = api._activity_use_case()
    assert isinstance(use_case, ListRecentActivityUseCase)
    assert isinstance(use_case.repository, DjangoWarehouseEventRepository)


LOCMEM_CACHES = {
    name: {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': f'{name}-activity'}
    for name in ('default', 'access', 'auth')
}


def _get(path: str):
    user_id = uuid.uuid4()
    request = APIRequestFactory().get(path)
    force_authenticate(request, user=SimpleNamespace(id=user_id, pk=user_id, is_authenticated=True))
    return api.RecentActivityView.as_view()(request)


@pytest.fixture
def member():
    with override_settings(CACHES=LOCMEM_CACHES), \
            patch.object(api.IsCompanyMember, 'has_permission', return_value=True):
        yield


@pytest.mark.usefixtures('member')
class TestRecentActivityView:

    def test_returns_items_in_english_envelope(self):
        entry = _entry(detail='DSP-1042', reference_type='Dispatch', reference_id='dsp-1')
        with patch.object(api, '_activity_use_case') as factory:
            factory.return_value.execute.return_value = [entry]
            response = _get('/recent-activity/')

        assert response.status_code == 200
        assert response.data['message'] == 'Recent activity loaded.'
        item = response.data['data']['items'][0]
        assert item['event_type'] == 'dispatches.exited'
        assert item['detail'] == 'DSP-1042'
        assert 'payload' not in item
        factory.return_value.execute.assert_called_once_with(RECENT_ACTIVITY_LIMIT)

    def test_forwards_bounded_limit(self):
        with patch.object(api, '_activity_use_case') as factory:
            factory.return_value.execute.return_value = []
            response = _get('/recent-activity/?limit=5')
        assert response.status_code == 200
        factory.return_value.execute.assert_called_once_with(5)

    @pytest.mark.parametrize('query', ['limit=16', 'limit=0', 'limit=abc', 'unknown=1'])
    def test_rejects_invalid_query(self, query):
        with patch.object(api, '_activity_use_case') as factory:
            response = _get(f'/recent-activity/?{query}')
        assert response.status_code == 400
        factory.assert_not_called()
