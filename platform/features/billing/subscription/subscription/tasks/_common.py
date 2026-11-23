"""Shared wiring for the subscription Celery tasks.

Centralises what the downgrade and renewal tasks would otherwise duplicate:
the per-company expiry lock key + TTL, the charge use-case factory, and the
per-company daily-sweep scaffolding (iterate due companies → lock → run →
tally, isolating per-company failures). The tasks stay thin: they only supply
the work function and how to read its outcome.
"""
import logging
from collections import Counter

from core.tasks.base import redis_lock

logger = logging.getLogger('app.tasks')

# The lock is held for the whole task body; the TTL matches the tasks' hard
# ``time_limit`` so the lock outlives the work it guards.
LOCK_TTL_SECONDS = 900


def company_lock_key(company_id) -> str:
    """Shared by the downgrade AND renewal tasks so a company's expiry is
    processed by exactly one flow at a time (downgrade OR renewal — mutually
    exclusive), and the shared lock guards against edge races."""
    return f'subscription:expiry:{company_id}'


def build_charge_use_case():
    """``CreateChargeUseCase`` wired with DB repo, router, and currency policy.
    Deferred imports avoid app-load cycles."""
    from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
    from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
    from platform.features.billing.commerce.payments.infrastructure.routing.router import DefaultPaymentRouter
    from platform.features.billing.commerce.payments.integration.adapters.country_currency_policy import (
        DjangoCountryCurrencyPolicy,
    )
    return CreateChargeUseCase(
        DjangoChargeRepository(),
        DefaultPaymentRouter(),
        currency_policy=DjangoCountryCurrencyPolicy(),
    )


def run_company_sweep(task, company_ids, process, tally) -> dict:
    """Per-company daily-sweep scaffolding shared by the two Beat tasks.

    For each company: take its lock (skip if already held), run
    ``process(company_id)``, map the outcome to a count bucket via
    ``tally(outcome)``, and isolate failures — one company's error never aborts
    the sweep. Returns ``{'due': N, <bucket>: count, ...}`` and logs it.
    """
    counts = Counter()
    for cid in company_ids:
        with redis_lock(company_lock_key(cid), ttl_seconds=LOCK_TTL_SECONDS) as acquired:
            if not acquired:
                counts['skipped_locked'] += 1
                continue
            try:
                outcome = process(cid)
            except Exception:
                counts['failed'] += 1
                logger.exception('%s: failed for company %s', task.name, cid)
                continue
            counts[tally(outcome)] += 1

    result = {'due': len(company_ids), **counts}
    logger.info('%s complete', task.name,
                extra={'task_id': task.request.id, 'task_name': task.name, **result})
    return result
