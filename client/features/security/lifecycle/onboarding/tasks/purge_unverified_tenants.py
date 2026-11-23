"""Celery task for the unverified-tenants sweep.

Companion to ``onboarding.purge_expired``: this one targets *finalised*
registrations whose admin user never confirmed their email. The
provisioned Company + schema sit unused in DB until this sweep removes
them.

Scheduled daily at 03:30 UTC by ``BEAT_SCHEDULE`` in
:mod:`core.tasks.schedules` (deliberately 30 minutes after
``onboarding.purge_expired`` so the two never compete for DB locks
or audit-log throughput). Manual invocations work too::

    from client.features.security.lifecycle.onboarding.tasks.purge_unverified_tenants import (
        purge_unverified_tenants,
    )
    purge_unverified_tenants.delay()                                         # async
    purge_unverified_tenants.apply(kwargs={'dry_run': True}).get()           # sync, dry-run
    purge_unverified_tenants.apply(kwargs={'retention_days': 14}).get()      # custom window

Lives at the *transport* layer: deserialises arguments, delegates to
:class:`PurgeUnverifiedTenantsUseCase`, logs counts. Any business
change (retention windows, candidate selection) goes in the use case —
this file should keep shrinking, not growing.
"""

import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock

from ..application.use_cases.purge_unverified_tenants import (
    PurgeUnverifiedTenantsUseCase,
)


logger = logging.getLogger('app.tasks')


@shared_task(
    base=BaseTask,
    name='onboarding.purge_unverified_tenants',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def purge_unverified_tenants(
    self,
    dry_run: bool = False,
    retention_days: int = 7,
) -> dict:
    """Daily sweep of finalised tenants whose users never confirmed.

    Wrapped in a Redis lock so a Beat clock-skew double-fire or a
    manual re-run during a retry never executes the body twice in
    parallel. The use case is already best-effort at the per-tenant
    level (it catches and logs per-row failures), but the lock keeps
    the audit trail clean (no overlapping "purge complete" entries
    with confusing counts).

    The lock TTL (15 min) is set safely above ``soft_time_limit`` (10
    min) so a worker that hits the soft limit and is killed still
    leaves the lock to expire on its own — no orphaned locks.
    """
    with redis_lock('onboarding:purge_unverified_tenants', ttl_seconds=900) as acquired:
        if not acquired:
            logger.info(
                'purge_unverified_tenants skipped — lock held',
                extra={'task_id': self.request.id, 'task_name': self.name},
            )
            return {'skipped': True}

        result = PurgeUnverifiedTenantsUseCase(
            retention_days=retention_days,
        ).execute(dry_run=dry_run)
        logger.info(
            'purge_unverified_tenants complete',
            extra={
                'task_id':         self.request.id,
                'task_name':       self.name,
                'dry_run':         dry_run,
                'retention_days':  retention_days,
                'tenants_deleted': result.tenants_deleted,
                'users_deleted':   result.users_deleted,
            },
        )
        return {
            'skipped':         False,
            'dry_run':         dry_run,
            'retention_days':  retention_days,
            'tenants_deleted': result.tenants_deleted,
            'users_deleted':   result.users_deleted,
        }
