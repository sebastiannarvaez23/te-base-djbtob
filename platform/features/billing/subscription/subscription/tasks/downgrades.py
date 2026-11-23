"""Celery tasks that materialise scheduled subscription downgrades.

Two entry points share the same per-company unit of work and lock, so the
daily sweep and the lazy (on-access) trigger can never double-charge a company:

  * ``subscription.apply_pending_downgrades`` — daily sweep (Beat); for
    inactive accounts.
  * ``subscription.apply_pending_downgrade_for_company`` — enqueued by the
    access middleware on the first request after vigencia; for active users.

Billing lives in the public schema (SHARED apps), so these are plain
``BaseTask`` — no per-tenant schema switching.
"""
import logging

from celery import shared_task

from core.tasks.base import BaseTask, redis_lock

from ._common import (
    LOCK_TTL_SECONDS,
    build_charge_use_case,
    company_lock_key,
    run_company_sweep,
)

logger = logging.getLogger('app.tasks')


def _build_use_case():
    from platform.features.billing.subscription.subscription.application.apply_pending_downgrades import (
        ApplyPendingDowngradesUseCase,
    )
    from platform.features.billing.subscription.subscription.application.change_subscription import (
        ChangeSubscriptionUseCase,
    )
    from platform.features.billing.subscription.subscription.infrastructure.repositories import (
        DjangoSubscriptionRepository,
    )

    change = ChangeSubscriptionUseCase(DjangoSubscriptionRepository(), build_charge_use_case())
    return ApplyPendingDowngradesUseCase(DjangoSubscriptionRepository(), change)


@shared_task(
    base=BaseTask,
    name='subscription.apply_pending_downgrades',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def apply_pending_downgrades(self) -> dict:
    """Daily sweep: apply every due pending downgrade. Each company is processed
    under its own lock (shared with the lazy task) to avoid double-charging."""
    use_case = _build_use_case()
    return run_company_sweep(
        self, use_case.due_company_ids(),
        process=use_case.apply_for_company,
        tally=lambda applied: 'applied' if applied else 'noop',
    )


@shared_task(
    base=BaseTask,
    name='subscription.apply_pending_downgrade_for_company',
    bind=True,
    soft_time_limit=120,
    time_limit=180,
)
def apply_pending_downgrade_for_company(self, company_id) -> dict:
    """Lazy trigger: materialise ONE company's pending downgrade right after
    its vigencia passes (enqueued by the access middleware)."""
    with redis_lock(company_lock_key(company_id), ttl_seconds=LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return {'skipped': True}
        try:
            applied = _build_use_case().apply_for_company(company_id)
        except Exception:
            logger.exception(
                'apply_pending_downgrade_for_company: failed for company %s', company_id,
            )
            raise
        return {'applied': bool(applied)}
