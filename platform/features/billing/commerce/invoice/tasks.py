"""Celery tasks for fiscal reconciliation with Neurana.

``issue_fiscal`` / ``void_fiscal`` remain only so messages already sitting in
the broker drain into the fiscal outbox; new work is enqueued there directly.
"""
from __future__ import annotations

import logging
from uuid import UUID

from celery import shared_task

logger = logging.getLogger('billing.invoice.tasks')


def _uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _outbox_repo():
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.repositories import (
        DjangoFiscalOutboxRepository,
    )

    return DjangoFiscalOutboxRepository()


@shared_task(name='invoice.issue_fiscal', ignore_result=True)
def issue_fiscal(invoice_id: str, charge_id: str | None = None) -> dict:
    from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
        EnqueueFiscalIssueUseCase,
    )

    inv, cid = _uuid(invoice_id), _uuid(charge_id)
    if inv is None or cid is None:
        return {'status': 'invalid_id'}
    EnqueueFiscalIssueUseCase(_outbox_repo()).execute(invoice_id=inv, charge_id=cid)
    return {'status': 'enqueued'}


@shared_task(name='invoice.void_fiscal', ignore_result=True)
def void_fiscal(invoice_id: str, reason: str = '', idempotency_key: str = '') -> dict:
    from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
        EnqueueFiscalVoidUseCase,
    )

    inv = _uuid(invoice_id)
    if inv is None:
        return {'status': 'invalid_id'}
    charge = _uuid((idempotency_key or '').removeprefix('void:'))
    EnqueueFiscalVoidUseCase(_outbox_repo()).execute(
        invoice_id=inv, charge_id=charge, reason=reason or 'charge_refunded',
    )
    return {'status': 'enqueued'}


@shared_task(name='invoice.reconcile_fiscal_pending', ignore_result=True)
def reconcile_fiscal_pending(*, limit: int = 100) -> dict:
    from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
        ReconcileFiscalOutboxUseCase,
    )
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.repositories import (
        DjangoFiscalInvoiceLookup,
    )
    from platform.features.billing.commerce.invoice.application.fiscal_issue import (
        ReconcileFiscalPendingUseCase,
    )
    from platform.features.billing.commerce.invoice.infrastructure.fiscal import (
        get_fiscal_invoicing_provider,
    )
    from platform.features.billing.commerce.invoice.infrastructure.fiscal.local import (
        LocalFiscalInvoicingProvider,
    )

    provider = get_fiscal_invoicing_provider()
    if isinstance(provider, LocalFiscalInvoicingProvider):
        return {'status': 'skipped_local'}
    polled = ReconcileFiscalPendingUseCase(provider).execute(limit=limit)
    enqueued = ReconcileFiscalOutboxUseCase(
        _outbox_repo(), DjangoFiscalInvoiceLookup(),
    ).execute(limit=limit)
    return {**polled, **enqueued}
