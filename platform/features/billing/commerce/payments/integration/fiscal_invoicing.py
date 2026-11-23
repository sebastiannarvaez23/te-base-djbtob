"""Neurana fiscal issue/void after billing events (never blocks the charge).

Commands are written to the fiscal outbox inside the caller's transaction, so
they commit (or roll back) together with the invoice change; the relay sends
them to Neurana with retries.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from django.db import transaction

from core.trace import get_trace_id
from platform.features.billing.commerce.invoice.infrastructure.fiscal import (
    get_fiscal_invoicing_provider,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.local import (
    LocalFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.models import Invoice
from platform.features.billing.commerce.payments.integration.events import InvoiceIssued

logger = logging.getLogger('billing.payments.fiscal')


def _outbox_repo():
    from platform.features.billing.commerce.fiscal_outbox.infrastructure.repositories import (
        DjangoFiscalOutboxRepository,
    )

    return DjangoFiscalOutboxRepository()


class FiscalInvoicingListener:
    """Enqueue the fiscal issue command; soft-fail never raises into the charge path."""

    def __init__(self, provider_factory=None, repository_factory=None):
        self._provider_factory = provider_factory or get_fiscal_invoicing_provider
        self._repository_factory = repository_factory or _outbox_repo

    def on_invoice_issued(self, event: InvoiceIssued) -> None:
        invoice_id: Optional[UUID] = event.invoice_id
        if invoice_id is None:
            return
        try:
            if isinstance(self._provider_factory(), LocalFiscalInvoicingProvider):
                return

            invoice = Invoice.objects.filter(pk=invoice_id).only(
                'id', 'fiscal_status', 'external_id', 'source_charge_id',
            ).first()
            if invoice is None:
                return
            if invoice.fiscal_status == Invoice.FiscalStatus.ISSUED and invoice.external_id:
                return

            charge_id = event.charge_id or invoice.source_charge_id
            if charge_id is None:
                logger.warning('Fiscal skip: no charge_id for invoice=%s', invoice_id)
                return

            from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
                EnqueueFiscalIssueUseCase,
            )
            from platform.features.billing.commerce.invoice.application.fiscal_issue import (
                mark_fiscal_pending,
            )

            # Savepoint: an outbox failure must not poison the charge transaction.
            with transaction.atomic():
                mark_fiscal_pending(invoice_id)
                EnqueueFiscalIssueUseCase(self._repository_factory()).execute(
                    invoice_id=invoice_id, charge_id=charge_id, trace_id=get_trace_id(),
                )
        except Exception:
            logger.exception('Fiscal listener failed invoice=%s', invoice_id)


class FiscalVoidOnRefundListener:
    """Full refund → enqueue Neurana void (the relay waits for a pending issue)."""

    def __init__(self, provider_factory=None, repository_factory=None):
        self._provider_factory = provider_factory or get_fiscal_invoicing_provider
        self._repository_factory = repository_factory or _outbox_repo

    def on_payment_refunded(self, event) -> None:
        try:
            if getattr(event, 'is_partial', False):
                return
            invoice_id = getattr(event, 'invoice_id', None)
            if invoice_id is None:
                return
            if isinstance(self._provider_factory(), LocalFiscalInvoicingProvider):
                return

            invoice = Invoice.objects.filter(pk=invoice_id).only(
                'id', 'fiscal_status', 'external_id',
            ).first()
            if invoice is None:
                return
            if invoice.fiscal_status in (
                Invoice.FiscalStatus.VOIDED,
                Invoice.FiscalStatus.VOIDING,
                Invoice.FiscalStatus.REJECTED,
            ):
                return

            from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
                EnqueueFiscalVoidUseCase,
            )

            with transaction.atomic():
                EnqueueFiscalVoidUseCase(self._repository_factory()).execute(
                    invoice_id=invoice_id,
                    charge_id=getattr(event, 'charge_id', None),
                    reason='charge_refunded',
                    trace_id=get_trace_id(),
                )
        except Exception:
            logger.exception('Fiscal void-on-refund failed invoice=%s', getattr(event, 'invoice_id', None))
