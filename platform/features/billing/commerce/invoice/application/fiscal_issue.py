"""Issue / void / reconcile fiscal documents via ``IFiscalInvoicingProvider``.

``issue`` / ``void`` are driven by the fiscal outbox relay and let the
provider's ``FiscalTransientError`` / ``FiscalRejectedError`` propagate.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from django.utils import timezone

from platform.features.billing.commerce.invoice.application.fiscal_payload import (
    build_fiscal_customer,
    build_fiscal_lines,
)
from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalIssueRequest,
    FiscalVoidRequest,
    IFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal import (
    get_fiscal_invoicing_provider,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.local import (
    LocalFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.models import Invoice

logger = logging.getLogger('billing.invoice.fiscal')


def _apply_result(invoice_id: UUID, result) -> None:
    Invoice.objects.filter(pk=invoice_id).update(
        external_id=result.external_id,
        fiscal_number=result.fiscal_number,
        fiscal_status=result.fiscal_status or Invoice.FiscalStatus.ISSUED,
        fiscal_payload=result.fiscal_payload or {},
        updated_at=timezone.now(),
    )


def mark_fiscal_pending(invoice_id: UUID) -> None:
    Invoice.objects.filter(pk=invoice_id, fiscal_status=Invoice.FiscalStatus.NONE).update(
        fiscal_status=Invoice.FiscalStatus.PENDING,
        updated_at=timezone.now(),
    )


def mark_fiscal_rejected(invoice_id: UUID, *, error_code: str = '') -> None:
    Invoice.objects.filter(pk=invoice_id).exclude(
        fiscal_status__in=[
            Invoice.FiscalStatus.ISSUED,
            Invoice.FiscalStatus.VOIDING,
            Invoice.FiscalStatus.VOIDED,
        ],
    ).update(
        fiscal_status=Invoice.FiscalStatus.REJECTED,
        updated_at=timezone.now(),
    )
    logger.warning('fiscal_rejected invoice=%s code=%s', invoice_id, error_code)


class IssueFiscalInvoiceUseCase:
    def __init__(self, provider: IFiscalInvoicingProvider | None = None):
        self.provider = provider or get_fiscal_invoicing_provider()

    def execute(self, invoice_id: UUID, charge_id: Optional[UUID] = None) -> dict:
        if isinstance(self.provider, LocalFiscalInvoicingProvider):
            return {'status': 'skipped_local'}

        invoice = Invoice.objects.select_related('company').filter(pk=invoice_id).first()
        if invoice is None:
            return {'status': 'missing'}
        if invoice.external_id and invoice.fiscal_status in (
            Invoice.FiscalStatus.ISSUED,
            Invoice.FiscalStatus.VOIDING,
            Invoice.FiscalStatus.VOIDED,
        ):
            return {'status': 'already_issued'}

        cid = charge_id or invoice.source_charge_id
        if cid is None:
            logger.warning('Fiscal issue skip: no charge_id invoice=%s', invoice_id)
            return {'status': 'no_charge'}

        mark_fiscal_pending(invoice_id)

        customer = build_fiscal_customer(invoice, company=invoice.company)
        if not (customer.get('tax_id') or '').strip():
            logger.warning('Fiscal issue pending: missing tenant_nit invoice=%s', invoice_id)
            return {'status': 'pending_missing_nit'}

        result = self.provider.issue(
            FiscalIssueRequest(
                charge_id=cid,
                invoice_id=invoice_id,
                external_ref=str(cid),
                issue_date=(invoice.issue_date or date.today()).isoformat(),
                currency=(invoice.currency or 'USD').upper(),
                customer=customer,
                lines=build_fiscal_lines(invoice),
                payment={
                    'status': 'paid',
                    'method': 'card',
                    'gateway_ref': str(cid),
                },
                metadata={'invoice_number': invoice.invoice_number},
            ),
        )
        if result is None:
            return {'status': 'pending'}
        _apply_result(invoice_id, result)
        return {'status': 'issued', 'external_id': result.external_id}


class VoidFiscalInvoiceUseCase:
    def __init__(self, provider: IFiscalInvoicingProvider | None = None):
        self.provider = provider or get_fiscal_invoicing_provider()

    def execute(
        self,
        invoice_id: UUID,
        *,
        reason: str = '',
        idempotency_key: str = '',
        issue_abandoned: bool = True,
    ) -> dict:
        if isinstance(self.provider, LocalFiscalInvoicingProvider):
            return {'status': 'skipped_local'}

        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if invoice is None:
            return {'status': 'missing'}
        if invoice.fiscal_status == Invoice.FiscalStatus.VOIDED:
            return {'status': 'already_voided'}
        if not invoice.external_id:
            if not issue_abandoned:
                return {'status': 'awaiting_issue'}
            # Nothing was ever issued in Neurana: the void is local only.
            Invoice.objects.filter(pk=invoice_id).update(
                fiscal_status=Invoice.FiscalStatus.VOIDED,
                updated_at=timezone.now(),
            )
            return {'status': 'voided_local'}

        result = self.provider.void(
            FiscalVoidRequest(
                external_id=invoice.external_id,
                reason=reason or 'charge_refunded',
                idempotency_key=idempotency_key or f'void:{invoice.external_id}',
            ),
        )
        if result is None:
            return {'status': 'pending'}
        remote_status = (result.fiscal_status or '').lower()
        if remote_status in ('voiding', 'pending'):
            Invoice.objects.filter(pk=invoice_id).update(
                fiscal_status=Invoice.FiscalStatus.VOIDING,
                fiscal_payload=result.fiscal_payload or invoice.fiscal_payload,
                updated_at=timezone.now(),
            )
            return {'status': 'voiding', 'external_id': invoice.external_id}
        Invoice.objects.filter(pk=invoice_id).update(
            fiscal_status=result.fiscal_status or Invoice.FiscalStatus.VOIDED,
            fiscal_payload=result.fiscal_payload or invoice.fiscal_payload,
            updated_at=timezone.now(),
        )
        return {'status': 'voided', 'external_id': invoice.external_id}


def _invoices_needing_fiscal_poll(*, limit: int) -> list:
    """Pending issue, in-flight void, or a completed void whose webhook never arrived."""
    seen: set = set()
    rows: list = []
    primary = list(
        Invoice.objects.filter(
            fiscal_status__in=[
                Invoice.FiscalStatus.PENDING,
                Invoice.FiscalStatus.VOIDING,
            ],
        )
        .exclude(external_id='')
        .order_by('updated_at')[:limit]
    )
    for invoice in primary:
        seen.add(invoice.pk)
        rows.append(invoice)
    remaining = limit - len(rows)
    if remaining <= 0:
        return rows
    from platform.features.billing.commerce.fiscal_outbox.models import FiscalOutboxEvent

    void_ids = list(
        FiscalOutboxEvent.objects.filter(
            kind=FiscalOutboxEvent.Kind.VOID,
            status=FiscalOutboxEvent.Status.DONE,
        )
        .exclude(invoice_id__in=seen)
        .order_by('-processed_at')[:remaining]
        .values_list('invoice_id', flat=True)
    )
    if not void_ids:
        return rows
    extras = list(
        Invoice.objects.filter(
            pk__in=void_ids,
            fiscal_status=Invoice.FiscalStatus.ISSUED,
        ).exclude(external_id='')
    )
    rows.extend(extras)
    return rows


class ReconcileFiscalPendingUseCase:
    """Poll Neurana for documents base knows about but never saw finalised
    (missed webhooks). Commands never sent are handled by the outbox reconcile."""

    def __init__(self, provider: IFiscalInvoicingProvider | None = None):
        self.provider = provider or get_fiscal_invoicing_provider()

    def execute(self, *, limit: int = 100) -> dict:
        if isinstance(self.provider, LocalFiscalInvoicingProvider):
            return {'scanned': 0, 'updated': 0, 'status': 'skipped_local'}

        qs = _invoices_needing_fiscal_poll(limit=limit)
        updated = 0
        from platform.features.billing.commerce.invoice.application.fiscal_webhook import (
            can_transition,
        )

        for invoice in qs:
            result = self.provider.get(invoice.external_id)
            if result is None:
                continue
            incoming = result.fiscal_status or invoice.fiscal_status
            if (
                incoming == invoice.fiscal_status
                and result.fiscal_number == invoice.fiscal_number
            ):
                continue
            if incoming != invoice.fiscal_status and not can_transition(
                invoice.fiscal_status or '', incoming,
            ):
                continue
            Invoice.objects.filter(pk=invoice.pk).update(
                fiscal_number=result.fiscal_number or invoice.fiscal_number,
                fiscal_status=incoming,
                fiscal_payload=result.fiscal_payload or invoice.fiscal_payload,
                external_id=result.external_id or invoice.external_id,
                updated_at=timezone.now(),
            )
            updated += 1
        logger.info('Fiscal reconcile scanned=%s updated=%s', len(qs), updated)
        return {'scanned': len(qs), 'updated': updated}
