"""Celery task: expire a company's stale period (auto_renew off, no pending change).

Enqueued by the access middleware on the first request after vigencia — never
run on the request path. The daily renewal sweep also expires leftover rows.
"""
import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock

from ._common import LOCK_TTL_SECONDS, company_lock_key

logger = logging.getLogger('app.tasks')


def _build_use_case():
    from platform.features.billing.subscription.subscription.application.expire_period import (
        ExpirePeriodUseCase,
    )
    from platform.features.billing.subscription.subscription.infrastructure.repositories import (
        DjangoSubscriptionRepository,
    )

    return ExpirePeriodUseCase(DjangoSubscriptionRepository())


@shared_task(
    base=BaseTask,
    name='subscription.expire_subscription_for_company',
    bind=True,
    soft_time_limit=60,
    time_limit=90,
)
def expire_subscription_for_company(self, company_id) -> dict:
    with redis_lock(company_lock_key(company_id), ttl_seconds=LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return {'skipped': True}
        try:
            expired = _build_use_case().execute(company_id)
        except Exception:
            logger.exception(
                'expire_subscription_for_company: failed for company %s', company_id,
            )
            raise
        return {'expired': expired}
