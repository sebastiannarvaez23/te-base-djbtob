import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from .billing_cycle import MONTHLY
from .schemas import (
    ActivePeriodSchema,
    CompanySubscriptionResultSchema,
    CreateSubscriptionSchema,
    PendingChangeSchema,
    PendingDowngradeDueSchema,
    SubscriptionSchema,
)


class IPlanCatalogRepository(ABC):
    """Catalog of sellable plans (admin CRUD + public listing)."""

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[SubscriptionSchema]:
        ...

    @abstractmethod
    def get_active(self) -> List[SubscriptionSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[SubscriptionSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[SubscriptionSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateSubscriptionSchema) -> SubscriptionSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: CreateSubscriptionSchema) -> Optional[SubscriptionSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def get_annual_discount_percent(self) -> Decimal:
        ...

    @abstractmethod
    def update_annual_discount_percent(self, percent: Decimal) -> Decimal:
        ...


class ICompanyPeriodRepository(ABC):
    """Company↔plan licenses (one row per paid/gift cycle)."""

    @abstractmethod
    def activate_plan(
        self,
        company_id: uuid.UUID,
        subscription_id: uuid.UUID,
        *,
        billing_interval: str = MONTHLY,
        charge_id: Optional[uuid.UUID] = None,
    ) -> CompanySubscriptionResultSchema:
        ...

    @abstractmethod
    def cancel(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def reactivate(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def active_plan_id(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        ...

    @abstractmethod
    def get_active_acquisition(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def active_billing_interval(self, company_id: uuid.UUID) -> str:
        ...

    @abstractmethod
    def pending_billing_interval(self, company_id: uuid.UUID) -> str:
        ...

    @abstractmethod
    def set_pending_downgrade(
        self,
        company_id: uuid.UUID,
        pending_subscription_id: uuid.UUID,
        *,
        billing_interval: Optional[str] = None,
    ) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def list_pending_downgrades_due(self) -> List[PendingDowngradeDueSchema]:
        ...

    @abstractmethod
    def get_pending_change(self, company_id: uuid.UUID) -> Optional[PendingChangeSchema]:
        ...

    @abstractmethod
    def get_due_pending_downgrade(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        ...

    @abstractmethod
    def get_renewal_due(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        ...

    @abstractmethod
    def list_renewals_due(self) -> List[uuid.UUID]:
        ...

    @abstractmethod
    def suspend(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def get_suspended_acquisition(
        self,
        company_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def restore_after_payment(
        self,
        company_id: uuid.UUID,
        *,
        charge_id: Optional[uuid.UUID] = None,
    ) -> Optional[CompanySubscriptionResultSchema]:
        ...

    @abstractmethod
    def expire_due(self, company_id: uuid.UUID | None = None) -> int:
        ...


class IActivePeriodLookup(ABC):
    @abstractmethod
    def get(self, company_id: uuid.UUID) -> Optional[ActivePeriodSchema]:
        ...


class ISubscriptionRepository(IPlanCatalogRepository, ICompanyPeriodRepository):
    """Composition-root convenience. Prefer the smaller ports in new code."""
