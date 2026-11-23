"""Fiscal invoicing port — Neurana (or local no-op) after a base invoice is issued."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID


class FiscalProviderError(Exception):
    """Remote fiscal call failed; ``code`` is the remote/internal error code."""

    def __init__(self, message: str = '', *, code: str = '', retry_after: float | None = None):
        super().__init__(message or code)
        self.code = code
        self.retry_after = retry_after


class FiscalTransientError(FiscalProviderError):
    """Outage / throttling / auth misconfig: retry later with backoff."""

    def __init__(self, message: str = '', *, code: str = '', retry_after: float | None = None,
                 circuit_open: bool = False):
        super().__init__(message, code=code, retry_after=retry_after)
        self.circuit_open = circuit_open


class FiscalRejectedError(FiscalProviderError):
    """Neurana refused the document (validation / business rule): do not retry."""


@dataclass(frozen=True)
class FiscalIssueRequest:
    charge_id: UUID
    invoice_id: UUID
    external_ref: str
    issue_date: str
    currency: str
    customer: dict[str, Any]
    lines: list[dict[str, Any]]
    payment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FiscalIssueResult:
    external_id: str
    fiscal_number: str
    fiscal_status: str
    fiscal_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FiscalVoidRequest:
    external_id: str
    reason: str = ''
    idempotency_key: str = ''


class IFiscalInvoicingProvider(ABC):
    """Only the fiscal outbox relay calls ``issue`` / ``void`` (never the charge path).

    Raise :class:`FiscalTransientError` / :class:`FiscalRejectedError` so the
    relay can retry or dead-letter; return ``None`` when the provider is a no-op.
    """

    @abstractmethod
    def issue(self, request: FiscalIssueRequest) -> Optional[FiscalIssueResult]:
        ...

    @abstractmethod
    def get(self, external_id: str) -> Optional[FiscalIssueResult]:
        """Soft read for reconciliation: ``None`` on any failure."""
        ...

    def void(self, request: FiscalVoidRequest) -> Optional[FiscalIssueResult]:
        return None
