"""Unit tests for task monitor catalog and use cases."""

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from django.utils import timezone

from core.errors import AppErrorCode, NotFoundException
from platform.features.support.ops.task_monitor.application.use_cases import (
    GetTaskRunLogsUseCase,
    GetTaskRunUseCase,
    ListMonitoredTasksUseCase,
    ListTaskRunsUseCase,
)
from platform.features.support.ops.task_monitor.domain.catalog import (
    TASK_CATALOG,
    get_task_def,
)
from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskRunLogsView,
    TaskRunSummaryView,
    TaskRunView,
)


pytestmark = pytest.mark.unit


def test_catalog_contains_reference_tasks():
    expected = {
        'onboarding.purge_expired',
        'onboarding.purge_unverified_tenants',
        'subscription.apply_pending_downgrades',
        'subscription.renew_due_subscriptions',
        'promotion.expire_vouchers',
        'promotion.revert_gift_benefits',
        'company.purge_closed_tenants',
    }
    assert expected <= set(TASK_CATALOG)
    assert 'task_monitor.demo_probe' not in TASK_CATALOG
    purge = get_task_def('onboarding.purge_expired')
    assert purge is not None
    assert [s.key for s in purge.steps] == [
        'acquire_lock',
        'expire_registrations',
        'delete_failed',
        'purge_tokens',
        'release',
    ]
    renew = get_task_def('subscription.renew_due_subscriptions')
    assert renew is not None
    assert [s.key for s in renew.steps] == [
        'acquire_lock', 'load_due', 'renew_companies', 'expire_stale', 'release',
    ]


def test_list_runs_returns_items_and_total():
    repo = MagicMock()
    run_id = uuid4()
    summary = TaskRunSummaryView(
        id=run_id,
        task_key='onboarding.purge_expired',
        status='success',
    )
    repo.list_runs.return_value = [summary]
    repo.count_runs.return_value = 1

    items, total = ListTaskRunsUseCase(repo).execute('onboarding.purge_expired')
    assert total == 1
    assert items[0].id == run_id
    repo.list_runs.assert_called_once()


def test_get_run_returns_view():
    repo = MagicMock()
    run_id = uuid4()
    repo.get_run.return_value = TaskRunView(
        id=run_id,
        task_key='onboarding.purge_expired',
        status='success',
        steps=[],
    )
    view = GetTaskRunUseCase(repo).execute(run_id)
    assert view.id == run_id
    assert view.status == 'success'


def test_list_tasks_filters_by_search_and_group():
    repo = MagicMock()
    repo.latest_run.return_value = None
    repo.count_recent_by_status.return_value = 0
    repo.has_running.return_value = False

    cards = ListMonitoredTasksUseCase(repo).execute(search='purge', group='onboarding')
    assert len(cards) == 2
    keys = {c.key for c in cards}
    assert keys == {
        'onboarding.purge_expired',
        'onboarding.purge_unverified_tenants',
    }


def test_list_runs_unknown_task_raises():
    repo = MagicMock()
    with pytest.raises(NotFoundException) as exc:
        ListTaskRunsUseCase(repo).execute('missing.task')
    assert exc.value.code == AppErrorCode.TASKMON_TASK_NOT_FOUND


def test_get_run_not_found():
    repo = MagicMock()
    repo.get_run.return_value = None
    with pytest.raises(NotFoundException) as exc:
        GetTaskRunUseCase(repo).execute(uuid4())
    assert exc.value.code == AppErrorCode.TASKMON_RUN_NOT_FOUND


def test_get_logs_returns_text():
    repo = MagicMock()
    run_id = uuid4()
    repo.get_run_logs.return_value = TaskRunLogsView(
        run_id=run_id, task_key='onboarding.purge_expired', log_text='ok',
    )
    logs = GetTaskRunLogsUseCase(repo).execute(run_id)
    assert logs.log_text == 'ok'


def test_list_tasks_filters_by_last_status():
    repo = MagicMock()
    now = timezone.now()
    summary = TaskRunSummaryView(
        id=uuid4(),
        task_key='onboarding.purge_expired',
        status='success',
        started_at=now - timedelta(hours=1),
        finished_at=now,
    )

    def latest(task_key):
        if task_key == 'onboarding.purge_expired':
            return summary
        return TaskRunSummaryView(
            id=uuid4(),
            task_key=task_key,
            status='failed',
            started_at=now,
        )

    repo.latest_run.side_effect = latest
    repo.count_recent_by_status.return_value = 1
    repo.has_running.return_value = False

    cards = ListMonitoredTasksUseCase(repo).execute(status='success')
    assert all(c.last_run and c.last_run.status == 'success' for c in cards)
    assert any(c.key == 'onboarding.purge_expired' for c in cards)
