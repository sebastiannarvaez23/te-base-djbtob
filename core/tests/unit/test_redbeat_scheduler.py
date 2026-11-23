"""Unit tests for the base RedBeat lock recovery.

Beat must keep running when Redis no longer considers this process the
lock owner (Windows sleep, Docker pause, Redis restart). The tests mock
the Redis lock so they do not need a live broker.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from redis.exceptions import LockNotOwnedError

from core.tasks.scheduler import BaseRedBeatScheduler

pytestmark = pytest.mark.unit


def _scheduler(*, lock=None) -> BaseRedBeatScheduler:
    sched = BaseRedBeatScheduler.__new__(BaseRedBeatScheduler)
    sched.lock_key = 'redbeat::lock'
    sched.lock_timeout = 600
    sched.max_interval = 300
    sched.lock = lock
    sched.app = MagicMock()
    return sched


class TestRenewLock:

    def test_extend_success_does_not_reacquire(self):
        lock = MagicMock()
        sched = _scheduler(lock=lock)
        sched._acquire_lock = MagicMock()

        sched._renew_lock()

        lock.extend.assert_called_once_with(600)
        sched._acquire_lock.assert_not_called()
        assert sched.lock is lock

    def test_reacquires_when_extend_raises_lock_not_owned(self):
        lock = MagicMock()
        lock.extend.side_effect = LockNotOwnedError('gone')
        sched = _scheduler(lock=lock)
        sched._acquire_lock = MagicMock()

        sched._renew_lock()

        lock.release.assert_called_once()
        sched._acquire_lock.assert_called_once()

    def test_release_error_on_stale_lock_does_not_block_reacquire(self):
        lock = MagicMock()
        lock.extend.side_effect = LockNotOwnedError('gone')
        lock.release.side_effect = LockNotOwnedError('still gone')
        sched = _scheduler(lock=lock)
        sched._acquire_lock = MagicMock()

        sched._renew_lock()

        sched._acquire_lock.assert_called_once()

    def test_acquires_when_lock_missing(self):
        sched = _scheduler(lock=None)
        sched._acquire_lock = MagicMock()

        sched._renew_lock()

        sched._acquire_lock.assert_called_once()


class TestAcquireLock:

    @patch('core.tasks.scheduler.get_redis')
    def test_registers_extend_script_and_stores_lock(self, mock_get_redis):
        redis_client = MagicMock()
        mock_get_redis.return_value = redis_client
        lock = MagicMock()
        redis_client.lock.return_value = lock
        script = object()
        redis_client.register_script.return_value = script

        sched = _scheduler(lock=None)
        sched._acquire_lock()

        redis_client.lock.assert_called_once_with(
            'redbeat::lock', timeout=600, sleep=300,
        )
        redis_client.register_script.assert_called_once()
        lock.acquire.assert_called_once()
        assert lock.lua_extend is script
        assert sched.lock is lock


class TestTickDelegatesAfterRenew:

    @patch('redbeat.schedulers.RedBeatScheduler.tick', return_value=12.0)
    def test_renews_lock_skips_parent_extend_restores_key(self, parent_tick):
        sched = _scheduler(lock=MagicMock())
        sched._renew_lock = MagicMock()

        result = BaseRedBeatScheduler.tick(sched)

        sched._renew_lock.assert_called_once()
        parent_tick.assert_called_once()
        assert result == 12.0
        assert sched.lock_key == 'redbeat::lock'
