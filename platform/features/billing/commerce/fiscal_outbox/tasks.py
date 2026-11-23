"""Celery entry points for the fiscal outbox (scheduled in ``core/tasks/schedules.py``)."""
from __future__ import annotations

from celery import shared_task
from django.conf import settings


@shared_task(name='billing.fiscal_outbox.relay', ignore_result=True)
def relay_fiscal_outbox(limit: int = 200) -> dict:
    from core.trace import set_trace_id
    from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
        RelayFiscalOutboxUseCase,
    )
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.gateway import (
        InvoiceFiscalDocumentGateway,
    )
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.repositories import (
        DjangoFiscalOutboxRepository,
    )

    try:
        return RelayFiscalOutboxUseCase(
            DjangoFiscalOutboxRepository(),
            InvoiceFiscalDocumentGateway(),
            max_age_hours=float(getattr(settings, 'FISCAL_OUTBOX_MAX_AGE_HOURS', 72)),
            bind_trace=set_trace_id,
        ).execute(limit=limit).model_dump()
    finally:
        set_trace_id('-')


@shared_task(name='billing.fiscal_outbox.check_health', ignore_result=True)
def check_fiscal_sync_health() -> dict:
    from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
        CheckFiscalSyncHealthUseCase,
    )
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.alert_notifier import (
        FiscalSyncAlertNotifier,
    )
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.repositories import (
        DjangoFiscalOutboxRepository,
    )

    return CheckFiscalSyncHealthUseCase(
        DjangoFiscalOutboxRepository(),
        FiscalSyncAlertNotifier(),
        pending_minutes=int(getattr(settings, 'FISCAL_ALERT_PENDING_MINUTES', 15)),
    ).execute()
