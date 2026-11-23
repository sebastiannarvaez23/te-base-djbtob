import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import (
    AdminRefundTicketSchema,
    CreateRefundTicketSchema,
    PeriodSnapshot,
    PayoutResult,
    RefundNotification,
    RefundTicketSchema,
    RefundableCharge,
)


class IRefundRequestRepository(ABC):
    @abstractmethod
    def create(self, data: CreateRefundTicketSchema) -> RefundTicketSchema:
        ...

    @abstractmethod
    def get_by_id(self, ticket_id: uuid.UUID, company_id: uuid.UUID | None = None) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def get_open(self, company_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def get_latest(self, company_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def last_accepted_at(self, company_id: uuid.UUID) -> Optional[datetime]:
        ...

    @abstractmethod
    def mark_processing(self, ticket_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def mark_completed(
        self, ticket_id: uuid.UUID, *, gateway_refund_id: str,
    ) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def mark_failed(self, ticket_id: uuid.UUID, *, error: str) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def mark_approved(
        self,
        ticket_id: uuid.UUID,
        *,
        approved_by_id: Optional[uuid.UUID],
        payout_due_on: date,
    ) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def mark_rejected(
        self, ticket_id: uuid.UUID, *, reason: str,
    ) -> Optional[RefundTicketSchema]:
        ...

    @abstractmethod
    def list_admin(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_admin(self, ticket_id: uuid.UUID) -> Optional[AdminRefundTicketSchema]:
        ...


class IPeriodSnapshotLookup(ABC):
    @abstractmethod
    def get_active(self, company_id: uuid.UUID) -> Optional[PeriodSnapshot]:
        ...


class IRefundableChargeLookup(ABC):
    @abstractmethod
    def get_for_period(self, company_id: uuid.UUID, period_id: uuid.UUID) -> Optional[RefundableCharge]:
        """Captured cobro for ``period_id``, or an unbound cobro of the same company.

        Never returns a charge bound to a different period.
        """
        ...


class IRefundPayoutPort(ABC):
    """Money return. Today: charge gateway. Tomorrow: Stripe/Wompi adapters."""

    @abstractmethod
    def refund(self, charge_id: uuid.UUID, amount: Decimal, reason: str) -> PayoutResult:
        ...


class IRefundNotifier(ABC):
    @abstractmethod
    def notify(self, message: RefundNotification, user_ids: list[uuid.UUID]) -> None:
        ...


class ICompanyRecipientLookup(ABC):
    @abstractmethod
    def active_user_ids(self, schema_name: str) -> list[uuid.UUID]:
        ...
