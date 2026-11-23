from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from platform.features.billing.commerce.fiscal_outbox.domain.schemas import (
    EnqueueFiscalOutboxSchema,
    FiscalBacklogSchema,
    FiscalDeadReason,
    FiscalOutboxEventSchema,
    FiscalOutboxKind,
)


class IFiscalOutboxRepository(ABC):
    @abstractmethod
    def enqueue(self, data: EnqueueFiscalOutboxSchema) -> tuple[FiscalOutboxEventSchema, bool]:
        """Idempotent on ``idempotency_key``; returns ``(event, created)``."""

    @abstractmethod
    def claim_due(self, *, limit: int, lease_seconds: int) -> list[FiscalOutboxEventSchema]:
        """Lock due rows (skip locked) and lease them to this worker."""

    @abstractmethod
    def mark_done(self, event_id: UUID) -> None: ...

    @abstractmethod
    def reschedule(
        self,
        event_id: UUID,
        *,
        next_attempt_at: datetime,
        attempts: int,
        error: str = '',
        error_code: str = '',
    ) -> None: ...

    @abstractmethod
    def mark_dead(
        self,
        event_id: UUID,
        *,
        reason: FiscalDeadReason,
        error: str = '',
        error_code: str = '',
    ) -> None: ...

    @abstractmethod
    def latest_for_invoice(
        self, invoice_id: UUID, kind: FiscalOutboxKind,
    ) -> Optional[FiscalOutboxEventSchema]: ...

    @abstractmethod
    def has_event(self, invoice_id: UUID, kind: FiscalOutboxKind) -> bool: ...

    @abstractmethod
    def stale_pending(self, *, created_before: datetime) -> FiscalBacklogSchema: ...

    @abstractmethod
    def unalerted_dead(self, *, limit: int) -> list[FiscalOutboxEventSchema]: ...

    @abstractmethod
    def mark_alerted(self, event_ids: list[UUID]) -> None: ...


class IFiscalDocumentGateway(ABC):
    """base side of a fiscal command (loads the invoice, calls the provider,
    persists the result). Raises the fiscal port's transient/rejected errors."""

    @abstractmethod
    def issue(self, invoice_id: UUID, charge_id: Optional[UUID]) -> str:
        """Return an outcome status (``issued``, ``pending_missing_nit``, …)."""

    @abstractmethod
    def void(
        self, invoice_id: UUID, *, reason: str, idempotency_key: str, issue_abandoned: bool,
    ) -> str: ...

    @abstractmethod
    def mark_rejected(self, invoice_id: UUID, *, error_code: str) -> None: ...


class IFiscalInvoiceLookup(ABC):
    """Read side used by reconciliation to find commands never enqueued."""

    @abstractmethod
    def pending_without_document(self, *, limit: int) -> list[tuple[UUID, Optional[UUID]]]:
        """``(invoice_id, charge_id)`` with fiscal_status pending and no Neurana id."""

    @abstractmethod
    def cancelled_with_live_document(self, *, limit: int) -> list[tuple[UUID, Optional[UUID]]]:
        """Fully refunded base invoices whose Neurana document is still issued."""


class IFiscalSyncAlertNotifier(ABC):
    """Admin bell (campanita) alerts for the base→Neurana fiscal sync."""

    @abstractmethod
    def breaker_changed(self, *, previous: str, new: str) -> None: ...

    @abstractmethod
    def backlog_stale(self, *, count: int, oldest_minutes: int) -> None: ...

    @abstractmethod
    def dead_letters(self, events: list[FiscalOutboxEventSchema]) -> None: ...
