"""Celery tasks for automatic recurring subscription renewals.

Two entry points share the same per-company lock as the downgrade tasks
(``subscription:expiry:{company_id}``) so a company's expiry is processed by
exactly one flow at a time:

  * ``subscription.renew_due_subscriptions`` — daily sweep (Beat); inactive accounts.
  * ``subscription.renew_subscription_for_company`` — enqueued by the access
    middleware on the first request after vigencia; active users.

On success → charge + extend + SUB_INVOICING + invoice PDF. On failure → the
subscription is suspended + a SUB_SUSPENDED email is sent.
"""
import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock
from core.tasks.run_context import retry_meta_from_celery, track_task_run

from ._common import (
    LOCK_TTL_SECONDS,
    build_charge_use_case,
    company_lock_key,
    run_company_sweep,
)

logger = logging.getLogger('app.tasks')

# Maps RenewSubscriptionUseCase outcomes to sweep count buckets.
_OUTCOME_BUCKET = {'renewed': 'renewed', 'suspended': 'suspended', 'not_due': 'noop'}

_SWEEP_LOCK_KEY = 'subscription:renew_due_sweep'


def _build_use_case():
    from platform.features.billing.subscription.subscription.application.renew_subscription import (
        RenewSubscriptionUseCase,
    )
    from platform.features.billing.subscription.subscription.infrastructure.repositories import (
        DjangoSubscriptionRepository,
    )

    return RenewSubscriptionUseCase(DjangoSubscriptionRepository(), build_charge_use_case())


@shared_task(
    base=BaseTask,
    name='subscription.renew_due_subscriptions',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def renew_due_subscriptions(self) -> dict:
    """Daily sweep: renew every active acquisition past its vigencia (no pending
    change, auto_renew on). Each company under its own lock."""
    is_retry, retry_count = retry_meta_from_celery(self)
    with track_task_run(
        task_key='subscription.renew_due_subscriptions',
        celery_task_id=getattr(self.request, 'id', None),
        is_retry=is_retry,
        retry_count=retry_count,
        trigger='beat',
    ) as run:
        with redis_lock(_SWEEP_LOCK_KEY, ttl_seconds=LOCK_TTL_SECONDS) as acquired:
            with run.step('acquire_lock') as step:
                if not acquired:
                    step.message = 'lock held'
                    run.mark_skipped('lock held')
                    return {'skipped': True}
                step.message = 'acquired'

            use_case = _build_use_case()
            with run.step('load_due') as s1:
                company_ids = list(use_case.due_company_ids())
                s1.message = f'due={len(company_ids)}'

            with run.step('renew_companies') as s2:
                result = run_company_sweep(
                    self, company_ids,
                    process=use_case.renew_for_company,
                    tally=lambda outcome: _OUTCOME_BUCKET.get(outcome, 'noop'),
                )
                s2.message = str(result)

            with run.step('expire_stale') as s3:
                from platform.features.billing.subscription.subscription.application.expire_period import (
                    ExpirePeriodUseCase,
                )
                from platform.features.billing.subscription.subscription.infrastructure.repositories import (
                    DjangoSubscriptionRepository,
                )
                expired = ExpirePeriodUseCase(DjangoSubscriptionRepository()).execute()
                s3.message = f'expired={expired}'
                result = {**result, 'expired': expired}

            with run.step('release') as s4:
                s4.message = 'lock released'

            return result


@shared_task(
    base=BaseTask,
    name='subscription.renew_subscription_for_company',
    bind=True,
    soft_time_limit=120,
    time_limit=180,
)
def renew_subscription_for_company(self, company_id) -> dict:
    """Lazy trigger: renew ONE company's active plan right after its vigencia
    passes (enqueued by the access middleware)."""
    with redis_lock(company_lock_key(company_id), ttl_seconds=LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return {'skipped': True}
        try:
            outcome = _build_use_case().renew_for_company(company_id)
        except Exception:
            logger.exception('renew_subscription_for_company: failed for company %s', company_id)
            raise
        return {'outcome': outcome}
