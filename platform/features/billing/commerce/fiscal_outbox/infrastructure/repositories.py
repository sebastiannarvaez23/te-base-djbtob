from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from django.db import NotSupportedError, transaction
from django.db.models import Min, Q
from django.utils import timezone

from platform.features.billing.commerce.fiscal_outbox.domain.interfaces import (
    IFiscalInvoiceLookup,
    IFiscalOutboxRepository,
)
from platform.features.billing.commerce.fiscal_outbox.domain.schemas import (
    EnqueueFiscalOutboxSchema,
    FiscalBacklogSchema,
    FiscalDeadReason,
    FiscalOutboxEventSchema,
    FiscalOutboxKind,
)
from platform.features.billing.commerce.fiscal_outbox.models import FiscalOutboxEvent

_S = FiscalOutboxEvent.Status


def _to_schema(obj: FiscalOutboxEvent) -> FiscalOutboxEventSchema:
    return FiscalOutboxEventSchema.model_validate(obj)


class DjangoFiscalOutboxRepository(IFiscalOutboxRepository):
    def enqueue(self, data: EnqueueFiscalOutboxSchema) -> tuple[FiscalOutboxEventSchema, bool]:
        obj, created = FiscalOutboxEvent.objects.get_or_create(
            idempotency_key=data.idempotency_key,
            defaults={
                'kind': data.kind.value,
                'invoice_id': data.invoice_id,
                'charge_id': data.charge_id,
                'reason': data.reason,
                'trace_id': data.trace_id,
            },
        )
        return _to_schema(obj), created

    def claim_due(self, *, limit: int, lease_seconds: int) -> list[FiscalOutboxEventSchema]:
        now = timezone.now()
        due = FiscalOutboxEvent.objects.filter(
            Q(status=_S.PENDING, next_attempt_at__lte=now)
            # Worker died mid-call: lease expired, hand the row to someone else.
            | Q(status=_S.PROCESSING, locked_until__lt=now),
        ).order_by('next_attempt_at')
        with transaction.atomic():
            try:
                rows = list(due.select_for_update(skip_locked=True)[:limit])
            except NotSupportedError:
                rows = list(due.select_for_update()[:limit])
            if not rows:
                return []
            FiscalOutboxEvent.objects.filter(pk__in=[r.pk for r in rows]).update(
                status=_S.PROCESSING,
                locked_until=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        return [_to_schema(r) for r in rows]

    def mark_done(self, event_id: UUID) -> None:
        now = timezone.now()
        FiscalOutboxEvent.objects.filter(pk=event_id).update(
            status=_S.DONE, locked_until=None, processed_at=now, updated_at=now,
            last_error='', last_error_code='',
        )

    def reschedule(
        self,
        event_id: UUID,
        *,
        next_attempt_at: datetime,
        attempts: int,
        error: str = '',
        error_code: str = '',
    ) -> None:
        FiscalOutboxEvent.objects.filter(pk=event_id).update(
            status=_S.PENDING,
            attempts=attempts,
            next_attempt_at=next_attempt_at,
            locked_until=None,
            last_error=(error or '')[:2000],
            last_error_code=(error_code or '')[:40],
            updated_at=timezone.now(),
        )

    def mark_dead(
        self,
        event_id: UUID,
        *,
        reason: FiscalDeadReason,
        error: str = '',
        error_code: str = '',
    ) -> None:
        now = timezone.now()
        FiscalOutboxEvent.objects.filter(pk=event_id).update(
            status=_S.DEAD,
            dead_reason=reason.value,
            locked_until=None,
            processed_at=now,
            last_error=(error or '')[:2000],
            last_error_code=(error_code or '')[:40],
            updated_at=now,
        )

    def latest_for_invoice(
        self, invoice_id: UUID, kind: FiscalOutboxKind,
    ) -> Optional[FiscalOutboxEventSchema]:
        obj = (
            FiscalOutboxEvent.objects.filter(invoice_id=invoice_id, kind=kind.value)
            .order_by('-created_at')
            .first()
        )
        return _to_schema(obj) if obj else None

    def has_event(self, invoice_id: UUID, kind: FiscalOutboxKind) -> bool:
        return FiscalOutboxEvent.objects.filter(invoice_id=invoice_id, kind=kind.value).exists()

    def stale_pending(self, *, created_before: datetime) -> FiscalBacklogSchema:
        agg = FiscalOutboxEvent.objects.filter(
            status__in=[_S.PENDING, _S.PROCESSING], created_at__lt=created_before,
        ).aggregate(oldest=Min('created_at'))
        if agg['oldest'] is None:
            return FiscalBacklogSchema()
        count = FiscalOutboxEvent.objects.filter(
            status__in=[_S.PENDING, _S.PROCESSING], created_at__lt=created_before,
        ).count()
        return FiscalBacklogSchema(count=count, oldest_created_at=agg['oldest'])

    def unalerted_dead(self, *, limit: int) -> list[FiscalOutboxEventSchema]:
        rows = FiscalOutboxEvent.objects.filter(
            status=_S.DEAD, alerted_at__isnull=True,
        ).order_by('processed_at')[:limit]
        return [_to_schema(r) for r in rows]

    def mark_alerted(self, event_ids: list[UUID]) -> None:
        if event_ids:
            FiscalOutboxEvent.objects.filter(pk__in=event_ids).update(alerted_at=timezone.now())


class DjangoFiscalInvoiceLookup(IFiscalInvoiceLookup):
    def pending_without_document(self, *, limit: int) -> list[tuple[UUID, Optional[UUID]]]:
        from platform.features.billing.commerce.invoice.models import Invoice

        return list(
            Invoice.objects.filter(fiscal_status=Invoice.FiscalStatus.PENDING, external_id='')
            .order_by('updated_at')
            .values_list('id', 'source_charge_id')[:limit]
        )

    def cancelled_with_live_document(self, *, limit: int) -> list[tuple[UUID, Optional[UUID]]]:
        from platform.features.billing.commerce.invoice.models import Invoice

        return list(
            Invoice.objects.filter(
                status=Invoice.InvoiceStatus.CANCELLED,
                fiscal_status=Invoice.FiscalStatus.ISSUED,
            )
            .exclude(external_id='')
            .order_by('updated_at')
            .values_list('id', 'source_charge_id')[:limit]
        )
