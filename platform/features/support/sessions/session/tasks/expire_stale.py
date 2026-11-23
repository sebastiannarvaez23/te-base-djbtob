"""Celery task: cancel timed-out QUEUED sessions and close stale AWAITING_RATING."""

from __future__ import annotations

import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock
from platform.features.support.sessions.session.application import factory as session_factory

logger = logging.getLogger('app.tasks')

_LOCK_TTL = 300


@shared_task(
    base=BaseTask,
    name='support.expire_stale_sessions',
    bind=True,
    soft_time_limit=120,
    time_limit=180,
)
def expire_stale_support_sessions(self) -> dict:
    """Periodic sweeper for queue wait + rating TTL."""
    with redis_lock('support:expire_stale_sessions', ttl_seconds=_LOCK_TTL) as acquired:
        if not acquired:
            logger.info(
                'expire_stale_support_sessions skipped — lock held',
                extra={'task_id': self.request.id, 'task_name': self.name},
            )
            return {'skipped': True}

        result = session_factory.build_expire_stale().execute()
        logger.info(
            'expire_stale_support_sessions complete',
            extra={
                'task_id': self.request.id,
                'task_name': self.name,
                **result,
            },
        )
        return {'skipped': False, **result}
