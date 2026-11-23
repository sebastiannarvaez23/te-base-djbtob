"""Unit tests for TaskRunContext + compensation (rollback) stack."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.tasks.compensation import CompensationStack, format_compensation_log
from core.tasks.progress_port import (
    NullTaskProgressReporter,
    get_task_progress_reporter,
    set_task_progress_reporter,
)
from core.tasks.run_context import track_task_run


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_reporter():
    previous = get_task_progress_reporter()
    yield
    set_task_progress_reporter(previous)


def test_null_reporter_is_default_safe():
    set_task_progress_reporter(None)
    reporter = get_task_progress_reporter()
    assert isinstance(reporter, NullTaskProgressReporter)
    run_id = reporter.start_run(
        task_key='x', celery_task_id=None, is_retry=False, retry_count=0, trigger='beat',
    )
    assert run_id is not None


def test_track_task_run_emits_steps_and_success():
    reporter = MagicMock()
    run_id = uuid4()
    reporter.start_run.return_value = run_id
    set_task_progress_reporter(reporter)

    with track_task_run(
        task_key='onboarding.purge_expired',
        celery_task_id='celery-1',
        is_retry=True,
        retry_count=2,
        trigger='beat',
    ) as run:
        with run.step('acquire_lock', order=1) as step:
            step.message = 'acquired'
        with run.step('expire_registrations', order=2):
            pass

    assert reporter.start_run.called
    assert reporter.mark_running.called
    assert reporter.start_step.call_count == 2
    assert reporter.finish_step.call_count == 2
    assert reporter.finish_run.call_args.kwargs['status'] == 'success'


def test_track_task_run_marks_failed_on_exception():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)

    with pytest.raises(ValueError):
        with track_task_run(task_key='onboarding.purge_expired', celery_task_id='c4'):
            raise ValueError('boom')

    assert reporter.finish_run.call_args.kwargs['status'] == 'failed'
    assert 'boom' in reporter.finish_run.call_args.kwargs['error_summary']


def test_step_failure_propagates_and_marks_step_failed():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)

    with pytest.raises(RuntimeError):
        with track_task_run(task_key='onboarding.purge_expired', celery_task_id='c6') as run:
            with run.step('acquire_lock', order=1):
                raise RuntimeError('lock error')

    finish_step = reporter.finish_step.call_args.kwargs
    assert finish_step['status'] == 'failed'
    assert 'lock error' in finish_step['error_detail']
    assert 'Traceback' in finish_step['error_detail']
    assert reporter.finish_run.call_args.kwargs['status'] == 'failed'
    assert '--- traceback ---' in reporter.finish_run.call_args.kwargs['log_text']
    assert 'lock error' in reporter.finish_run.call_args.kwargs['log_text']


def test_mark_skipped():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)

    with track_task_run(task_key='onboarding.purge_expired', celery_task_id='c7') as run:
        run.mark_skipped('lock held')

    assert reporter.finish_run.call_args.kwargs['status'] == 'skipped'


def test_compensation_stack_runs_lifo():
    order: list[str] = []
    stack = CompensationStack()
    stack.push('a', lambda: order.append('a'))
    stack.push('b', lambda: order.append('b'))
    stack.push('c', lambda: order.append('c'))
    results = stack.run_all()
    assert order == ['c', 'b', 'a']
    assert all(r.ok for r in results)
    assert format_compensation_log(results).count('OK') == 3


def test_compensation_stack_continues_after_undo_failure():
    order: list[str] = []
    stack = CompensationStack()
    stack.push('a', lambda: order.append('a'))
    stack.push('bad', lambda: (_ for _ in ()).throw(RuntimeError('undo boom')))
    stack.push('c', lambda: order.append('c'))
    results = stack.run_all()
    assert order == ['c', 'a']
    assert results[0].ok and results[0].label == 'c'
    assert not results[1].ok and results[1].label == 'bad'
    assert results[2].ok and results[2].label == 'a'


def test_failed_run_executes_compensations_lifo_and_logs():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)
    undone: list[str] = []

    with pytest.raises(RuntimeError):
        with track_task_run(task_key='demo', celery_task_id='c8') as run:
            with run.step('boot', order=1) as step:
                step.compensate('undo_boot', lambda: undone.append('boot'))
            with run.step('work', order=2) as step:
                step.compensate('undo_work', lambda: undone.append('work'))
            with run.step('persist', order=3):
                raise RuntimeError('persist failed')

    assert undone == ['work', 'boot']
    log_text = reporter.finish_run.call_args.kwargs['log_text']
    assert '--- compensations (rollback LIFO) ---' in log_text
    assert 'OK  undo_work' in log_text
    assert 'OK  undo_boot' in log_text
    assert 'rolled back' in reporter.finish_run.call_args.kwargs['error_summary']


def test_mark_failed_also_runs_compensations():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)
    undone: list[str] = []

    with track_task_run(task_key='demo', celery_task_id='c9') as run:
        with run.step('boot') as step:
            step.compensate('undo_boot', lambda: undone.append('boot'))
        run.mark_failed('intentional')

    assert undone == ['boot']
    assert reporter.finish_run.call_args.kwargs['status'] == 'failed'
    assert 'compensations' in reporter.finish_run.call_args.kwargs['log_text']


def test_success_discards_compensations_without_running():
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)
    undone: list[str] = []

    with track_task_run(task_key='demo', celery_task_id='c10') as run:
        with run.step('boot') as step:
            step.compensate('undo_boot', lambda: undone.append('boot'))

    assert undone == []
    assert 'compensations' not in reporter.finish_run.call_args.kwargs['log_text']


def test_failed_step_does_not_register_its_own_compensation():
    """Compensate is only registered after commit; a failing step has none."""
    reporter = MagicMock()
    reporter.start_run.return_value = uuid4()
    set_task_progress_reporter(reporter)
    undone: list[str] = []

    with pytest.raises(RuntimeError):
        with track_task_run(task_key='demo', celery_task_id='c11') as run:
            with run.step('boot') as step:
                step.compensate('undo_boot', lambda: undone.append('boot'))
            with run.step('work') as step:
                raise RuntimeError('before compensate')
                step.compensate('undo_work', lambda: undone.append('work'))  # noqa: F841

    assert undone == ['boot']
