"""Celery task for closed-tenant purge after the grace window."""

import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock

from ..application.purge_company import PurgeDueClosedCompaniesUseCase
from ..infrastructure.export_store import MinioTenantExportStore
from ..infrastructure.offboarding import DjangoCompanyOffboardingRepository


logger = logging.getLogger('app.tasks')


@shared_task(
    base=BaseTask,
    name='company.purge_closed_tenants',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def purge_closed_tenants(self, dry_run: bool = False) -> dict:
    with redis_lock('company:purge_closed_tenants', ttl_seconds=900) as acquired:
        if not acquired:
            logger.info(
                'purge_closed_tenants skipped — lock held',
                extra={'task_id': self.request.id, 'task_name': self.name},
            )
            return {'skipped': True}

        result = PurgeDueClosedCompaniesUseCase(
            DjangoCompanyOffboardingRepository(),
            MinioTenantExportStore(),
        ).execute(dry_run=dry_run)
        logger.info(
            'purge_closed_tenants complete',
            extra={
                'task_id': self.request.id,
                'task_name': self.name,
                **result,
            },
        )
        return {'skipped': False, **result}
