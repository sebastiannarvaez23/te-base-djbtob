"""Fiscal outbox: enqueue (in the invoice transaction), relay and health check."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import UUID

from platform.features.billing.commerce.fiscal_outbox.domain.interfaces import (
    IFiscalDocumentGateway,
    IFiscalInvoiceLookup,
    IFiscalOutboxRepository,
    IFiscalSyncAlertNotifier,
)
from platform.features.billing.commerce.fiscal_outbox.domain.retry_policy import (
    AWAIT_ISSUE_SECONDS,
    is_expired,
    next_delay_seconds,
)
from platform.features.billing.commerce.fiscal_outbox.domain.schemas import (
    EnqueueFiscalOutboxSchema,
    FiscalDeadReason,
    FiscalOutboxEventSchema,
    FiscalOutboxKind,
    FiscalOutboxStatus,
    RelayResultSchema,
)
from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalRejectedError,
    FiscalTransientError,
)

logger = logging.getLogger('billing.fiscal_outbox')

# Gateway outcomes that mean "nothing sent yet, try again later".
DEFERRED_OUTCOMES = frozenset({'pending', 'pending_missing_nit'})
_ACTIVE = (FiscalOutboxStatus.PENDING, FiscalOutboxStatus.PROCESSING)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _trace(trace_id: str) -> str:
    value = (trace_id or '').strip()
    return '' if value == '-' else value[:64]


def issue_key(charge_id: UUID) -> str:
    return f'issue:{charge_id}'


def void_key(*, charge_id: Optional[UUID], invoice_id: UUID) -> str:
    return f'void:{charge_id or invoice_id}'


class EnqueueFiscalIssueUseCase:
    def __init__(self, repository: IFiscalOutboxRepository):
        self.repository = repository

    def execute(self, *, invoice_id: UUID, charge_id: UUID, trace_id: str = '') -> bool:
        _, created = self.repository.enqueue(EnqueueFiscalOutboxSchema(
            kind=FiscalOutboxKind.ISSUE,
            invoice_id=invoice_id,
            charge_id=charge_id,
            idempotency_key=issue_key(charge_id),
            trace_id=_trace(trace_id),
        ))
        return created


class EnqueueFiscalVoidUseCase:
    def __init__(self, repository: IFiscalOutboxRepository):
        self.repository = repository

    def execute(
        self,
        *,
        invoice_id: UUID,
        charge_id: Optional[UUID] = None,
        reason: str = 'charge_refunded',
        trace_id: str = '',
    ) -> bool:
        _, created = self.repository.enqueue(EnqueueFiscalOutboxSchema(
            kind=FiscalOutboxKind.VOID,
            invoice_id=invoice_id,
            charge_id=charge_id,
            idempotency_key=void_key(charge_id=charge_id, invoice_id=invoice_id),
            reason=(reason or '')[:200],
            trace_id=_trace(trace_id),
        ))
        return created


class RelayFiscalOutboxUseCase:
    """Drain due commands. Transient errors back off on the ladder; an open
    breaker parks the batch without consuming attempts; rejections dead-letter."""

    def __init__(
        self,
        repository: IFiscalOutboxRepository,
        gateway: IFiscalDocumentGateway,
        *,
        max_age_hours: float = 72,
        lease_seconds: int = 300,
        clock: Callable[[], datetime] = _utcnow,
        bind_trace: Callable[[str], None] | None = None,
    ):
        self.repository = repository
        self.gateway = gateway
        self.max_age_hours = max_age_hours
        self.lease_seconds = lease_seconds
        self._clock = clock
        self._bind_trace = bind_trace

    def execute(self, *, limit: int = 200) -> RelayResultSchema:
        result = RelayResultSchema()
        events = self.repository.claim_due(limit=limit, lease_seconds=self.lease_seconds)
        result.claimed = len(events)
        for index, event in enumerate(events):
            if self._bind_trace is not None and event.trace_id:
                self._bind_trace(event.trace_id)
            try:
                outcome = self._dispatch(event)
            except FiscalTransientError as exc:
                if exc.circuit_open:
                    self._park(events[index:], exc.retry_after)
                    result.circuit_open = True
                    break
                self._fail(event, result, error=str(exc), code=exc.code, retry_after=exc.retry_after)
            except FiscalRejectedError as exc:
                self._reject(event, exc)
                result.dead += 1
            except Exception as exc:  # noqa: BLE001 — never let one row kill the batch
                logger.exception('fiscal_outbox_unexpected id=%s', event.id)
                self._fail(event, result, error=str(exc)[:500], code='unexpected')
            else:
                if outcome == 'voiding':
                    self.repository.mark_done(event.id)
                    result.done += 1
                elif outcome == 'awaiting_issue':
                    self.repository.reschedule(
                        event.id,
                        next_attempt_at=self._clock() + timedelta(seconds=AWAIT_ISSUE_SECONDS),
                        attempts=event.attempts,
                        error_code='awaiting_issue',
                    )
                    result.deferred += 1
                elif outcome in DEFERRED_OUTCOMES:
                    self._fail(event, result, error=outcome, code=outcome)
                else:
                    self.repository.mark_done(event.id)
                    result.done += 1
        if result.claimed:
            logger.info('fiscal_outbox_relay %s', result.model_dump())
        return result

    def _dispatch(self, event: FiscalOutboxEventSchema) -> str:
        if event.kind == FiscalOutboxKind.ISSUE:
            return self.gateway.issue(event.invoice_id, event.charge_id)
        issue = self.repository.latest_for_invoice(event.invoice_id, FiscalOutboxKind.ISSUE)
        if issue is not None and issue.status in _ACTIVE:
            return 'awaiting_issue'
        return self.gateway.void(
            event.invoice_id,
            reason=event.reason,
            idempotency_key=event.idempotency_key,
            issue_abandoned=issue is None or issue.status == FiscalOutboxStatus.DEAD,
        )

    def _park(self, events: list[FiscalOutboxEventSchema], retry_after: float | None) -> None:
        wait = timedelta(seconds=max(1.0, float(retry_after or 30)))
        for event in events:
            self.repository.reschedule(
                event.id,
                next_attempt_at=self._clock() + wait,
                attempts=event.attempts,
                error='Neurana circuit open',
                error_code='ECO_012',
            )

    def _fail(
        self,
        event: FiscalOutboxEventSchema,
        result: RelayResultSchema,
        *,
        error: str,
        code: str,
        retry_after: float | None = None,
    ) -> None:
        now = self._clock()
        attempts = event.attempts + 1
        if is_expired(event.created_at, now, max_age_hours=self.max_age_hours):
            self.repository.mark_dead(
                event.id, reason=FiscalDeadReason.EXPIRED, error=error, error_code=code,
            )
            logger.error('fiscal_outbox_expired id=%s kind=%s invoice=%s code=%s',
                         event.id, event.kind.value, event.invoice_id, code)
            result.dead += 1
            return
        delay = next_delay_seconds(attempts, retry_after=retry_after)
        self.repository.reschedule(
            event.id,
            next_attempt_at=now + timedelta(seconds=delay),
            attempts=attempts,
            error=error,
            error_code=code,
        )
        result.retried += 1

    def _reject(self, event: FiscalOutboxEventSchema, exc: FiscalRejectedError) -> None:
        self.repository.mark_dead(
            event.id, reason=FiscalDeadReason.REJECTED, error=str(exc), error_code=exc.code,
        )
        if event.kind == FiscalOutboxKind.ISSUE:
            self.gateway.mark_rejected(event.invoice_id, error_code=exc.code)
        logger.error('fiscal_outbox_rejected id=%s kind=%s invoice=%s code=%s',
                     event.id, event.kind.value, event.invoice_id, exc.code)


class CheckFiscalSyncHealthUseCase:
    """Periodic bell alerts: stale backlog and new dead letters."""

    def __init__(
        self,
        repository: IFiscalOutboxRepository,
        notifier: IFiscalSyncAlertNotifier,
        *,
        pending_minutes: int = 15,
        clock: Callable[[], datetime] = _utcnow,
    ):
        self.repository = repository
        self.notifier = notifier
        self.pending_minutes = pending_minutes
        self._clock = clock

    def execute(self) -> dict:
        now = self._clock()
        backlog = self.repository.stale_pending(
            created_before=now - timedelta(minutes=self.pending_minutes),
        )
        if backlog.count and backlog.oldest_created_at is not None:
            oldest = int((now - backlog.oldest_created_at).total_seconds() // 60)
            self._safe(self.notifier.backlog_stale, count=backlog.count, oldest_minutes=oldest)

        dead = self.repository.unalerted_dead(limit=50)
        if dead:
            if self._safe(self.notifier.dead_letters, dead):
                self.repository.mark_alerted([e.id for e in dead])
        return {'stale_pending': backlog.count, 'dead_alerted': len(dead)}

    @staticmethod
    def _safe(fn, *args, **kwargs) -> bool:
        try:
            fn(*args, **kwargs)
            return True
        except Exception:  # noqa: BLE001 — alerts are best-effort
            logger.exception('fiscal_sync_alert_failed')
            return False


class ReconcileFiscalOutboxUseCase:
    """Daily safety net: re-enqueue commands the outbox never received."""

    def __init__(self, repository: IFiscalOutboxRepository, invoices: IFiscalInvoiceLookup):
        self.repository = repository
        self.invoices = invoices

    def execute(self, *, limit: int = 200) -> dict:
        issues = voids = 0
        for invoice_id, charge_id in self.invoices.pending_without_document(limit=limit):
            if charge_id is None or self.repository.has_event(invoice_id, FiscalOutboxKind.ISSUE):
                continue
            issues += int(EnqueueFiscalIssueUseCase(self.repository).execute(
                invoice_id=invoice_id, charge_id=charge_id,
            ))
        for invoice_id, charge_id in self.invoices.cancelled_with_live_document(limit=limit):
            if self.repository.has_event(invoice_id, FiscalOutboxKind.VOID):
                continue
            voids += int(EnqueueFiscalVoidUseCase(self.repository).execute(
                invoice_id=invoice_id, charge_id=charge_id, reason='charge_refunded',
            ))
        return {'issues_enqueued': issues, 'voids_enqueued': voids}
