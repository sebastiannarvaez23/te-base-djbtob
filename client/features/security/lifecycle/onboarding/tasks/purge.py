"""Celery task for the onboarding GC sweep.

Scheduled daily at 03:00 UTC by ``BEAT_SCHEDULE`` in
:mod:`core.tasks.schedules`. Manual invocations work too::

    from client.features.security.lifecycle.onboarding.tasks.purge import (
        purge_expired_onboardings,
    )
    purge_expired_onboardings.delay()                # async
    purge_expired_onboardings.apply(kwargs={'dry_run': True})  # sync, dry-run

Lives at the *transport* layer: deserialises arguments, delegates to
:class:`PurgeExpiredOnboardingsUseCase`, logs counts. Any business
change (retention windows, new sweep) goes in the use case — this file
should keep shrinking, not growing.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from core.tasks.base import BaseTask, redis_lock
from core.tasks.run_context import retry_meta_from_celery, track_task_run

from ..application.use_cases.purge_expired import PurgeExpiredOnboardingsUseCase


logger = logging.getLogger('app.tasks')


@shared_task(
    base=BaseTask,
    name='onboarding.purge_expired',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def purge_expired_onboardings(self, dry_run: bool = False) -> dict:
    """Daily sweep of expired onboarding rows + stale confirmation tokens.

    Wrapped in a Redis lock so a Beat clock-skew double-fire or a
    manual re-run during a retry never executes the body twice in
    parallel. The use case is already idempotent at the SQL level, but
    the lock keeps the audit trail clean (no overlapping
    "purge complete" entries with confusing counts).

    The lock TTL (15 min) is set safely above ``soft_time_limit`` (10
    min) so a worker that hits the soft limit and is killed still
    leaves the lock to expire on its own — no orphaned locks.
    """
    is_retry, retry_count = retry_meta_from_celery(self)
    with track_task_run(
        task_key='onboarding.purge_expired',
        celery_task_id=getattr(self.request, 'id', None),
        is_retry=is_retry,
        retry_count=retry_count,
        trigger='beat',
    ) as run:
        with redis_lock('onboarding:purge_expired', ttl_seconds=900) as acquired:
            with run.step('acquire_lock') as step:
                if not acquired:
                    step.message = 'lock held'
                    run.mark_skipped('lock held')
                    logger.info(
                        'purge_expired_onboardings skipped — lock held',
                        extra={'task_id': self.request.id, 'task_name': self.name},
                    )
                    return {'skipped': True}
                step.message = 'acquired'

            uc = PurgeExpiredOnboardingsUseCase()
            now = timezone.now()
            failed_cutoff = now - timedelta(days=uc.failed_retention_days)
            token_cutoff = now - timedelta(days=uc.token_retention_days)

            with run.step('expire_registrations') as s1:
                expired = uc.expire_in_progress(now, dry_run)
                s1.message = f'expired={expired}'
                # GC steps are intentionally one-way (idempotent sweeps).
                # Domain undos belong in use cases that mutate reversible
                # state; register ``step.compensate(...)`` there after commit.

            with run.step('delete_failed') as s2:
                failed_deleted = uc.delete_old_failed(failed_cutoff, dry_run)
                s2.message = f'deleted={failed_deleted}'

            with run.step('purge_tokens') as s3:
                tokens_deleted = uc.delete_old_tokens(token_cutoff, dry_run)
                s3.message = f'deleted={tokens_deleted}'

            with run.step('release') as s4:
                s4.message = 'lock released'

            logger.info(
                'purge_expired_onboardings complete',
                extra={
                    'task_id':        self.request.id,
                    'task_name':      self.name,
                    'dry_run':        dry_run,
                    'expired':        expired,
                    'failed_deleted': failed_deleted,
                    'tokens_deleted': tokens_deleted,
                },
            )
            return {
                'skipped':        False,
                'dry_run':        dry_run,
                'expired':        expired,
                'failed_deleted': failed_deleted,
                'tokens_deleted': tokens_deleted,
            }
