"""Domain ports for the promotion feature.

The repository port only persists/reads; it never returns ORM objects and never
owns redeem/validate business orchestration (that lives in the domain services
and the application use cases). Cross-feature needs (plans, charges, emails,
directory, invoices, onboarding) are expressed as narrow ports implemented by
infrastructure adapters and wired in ``composition.py``.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .schemas import (
    ActiveBenefitSchema,
    AdminSnapshot,
    BulkCreateResultSchema,
    ChargeSnapshot,
    CreateBenefitSchema,
    CreateBulkVouchersSchema,
    CreateRedemptionSchema,
    CreateVoucherSchema,
    PlanSnapshot,
    RedeemResultSchema,
    RedemptionSchema,
    VoucherSchema,
)


class IPromotionVoucherRepository(ABC):

    # ── vouchers: CRUD / listing ────────────────────────────────────────────

    @abstractmethod
    def create(self, data: CreateVoucherSchema, *, serial: Optional[str] = None) -> VoucherSchema:
        ...

    @abstractmethod
    def create_bulk(self, data: CreateBulkVouchersSchema) -> BulkCreateResultSchema:
        ...

    @abstractmethod
    def get_by_id(self, voucher_id: uuid.UUID) -> Optional[VoucherSchema]:
        ...

    @abstractmethod
    def get_by_serial(self, serial: str) -> Optional[VoucherSchema]:
        ...

    @abstractmethod
    def list_vouchers(self, **filters):
        """Return a PaginatedResult of vouchers."""
        ...

    @abstractmethod
    def list_redemptions(self, **filters) -> list[RedemptionSchema]:
        ...

    @abstractmethod
    def revoke(self, voucher_id: uuid.UUID) -> VoucherSchema:
        ...

    @abstractmethod
    def expire_due(self, *, now: datetime) -> int:
        ...

    @abstractmethod
    def next_serial(self, voucher_type: str) -> str:
        """Generate a unique serial for the given voucher type."""
        ...

    # ── benefits ────────────────────────────────────────────────────────────

    @abstractmethod
    def has_active_benefit(self, company_id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def get_active_benefit(
        self,
        company_id: uuid.UUID,
        *,
        subscription_id: Optional[uuid.UUID] = None,
    ) -> Optional[ActiveBenefitSchema]:
        ...

    @abstractmethod
    def list_active_benefits(
        self,
        company_id: uuid.UUID,
        *,
        status: Optional[str] = None,
    ) -> list[ActiveBenefitSchema]:
        ...

    @abstractmethod
    def list_gift_benefits_due_for_revert(self, *, now: datetime) -> list[ActiveBenefitSchema]:
        ...

    @abstractmethod
    def create_benefit(self, data: CreateBenefitSchema) -> ActiveBenefitSchema:
        ...

    @abstractmethod
    def complete_benefit(self, benefit_id: uuid.UUID) -> None:
        ...

    @abstractmethod
    def cancel_benefits(
        self,
        company_id: uuid.UUID,
        *,
        voucher_types: Optional[tuple[str, ...]] = None,
    ) -> int:
        ...

    @abstractmethod
    def decrement_discount_cycle(self, benefit_id: uuid.UUID) -> None:
        ...

    # ── redemption unit of work ─────────────────────────────────────────────

    @abstractmethod
    def find_redemption_by_idempotency(self, key: str) -> Optional[RedeemResultSchema]:
        ...

    @abstractmethod
    def persist_redeem(
        self,
        *,
        voucher_id: uuid.UUID,
        redemption: CreateRedemptionSchema,
        benefit: CreateBenefitSchema,
        activate_plan_id: Optional[uuid.UUID] = None,
    ) -> RedeemResultSchema:
        """Atomically lock the ACTIVE voucher, optionally activate a plan, create
        the redemption, mark the voucher REDEEMED and create the benefit."""
        ...

    @abstractmethod
    def rollback_redeem(
        self,
        *,
        company_id: uuid.UUID,
        voucher_serial: str,
        benefit_id: Optional[uuid.UUID],
        redemption_id: uuid.UUID,
        previous_plan_id: Optional[uuid.UUID],
        attempted_plan_id: uuid.UUID,
    ) -> None:
        ...

    # ── public purchase persistence ─────────────────────────────────────────

    @abstractmethod
    def find_by_checkout_idempotency(self, idempotency_key: str) -> Optional[VoucherSchema]:
        ...

    @abstractmethod
    def create_public_purchase_voucher(self, **kwargs) -> VoucherSchema:
        ...


class IPlanCatalogPort(ABC):

    @abstractmethod
    def get_active_plan(self, subscription_id: uuid.UUID) -> PlanSnapshot:
        ...

    @abstractmethod
    def get_company_active_plan(self, company_id: uuid.UUID) -> Optional[PlanSnapshot]:
        ...

    @abstractmethod
    def get_company_billing_interval(self, company_id: uuid.UUID) -> str:
        ...

    @abstractmethod
    def get_annual_discount_percent(self) -> Decimal:
        """Platform-wide discount applied to yearly charges (0–100)."""
        ...

    @abstractmethod
    def activate_plan(
        self, company_id: uuid.UUID, subscription_id: uuid.UUID, *, billing_interval: str = 'monthly',
    ) -> None:
        ...

    @abstractmethod
    def list_all_company_ids(self) -> list[uuid.UUID]:
        ...


class IPromotionChargePort(ABC):

    @abstractmethod
    def charge_plan(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        payment_method_id: Optional[uuid.UUID] = None,
        metadata: dict,
        description: str,
        processor_token: Optional[str] = None,
        card_data: Optional[dict] = None,
        buyer_name: str = '',
        buyer_email: str = '',
        idempotency_key: Optional[str] = None,
        currency: str = 'USD',
    ) -> ChargeSnapshot:
        ...

    @abstractmethod
    def bind_to_active_period(self, *, company_id: uuid.UUID, charge_id: uuid.UUID) -> None:
        """Stamp the cobro onto the company's current billing period."""
        ...


class IBillingCompanyPort(ABC):

    @abstractmethod
    def resolve_public_billing_company_id(self) -> uuid.UUID:
        ...


class IInvoiceBridgePort(ABC):

    @abstractmethod
    def find_invoice_id_for_charge(self, charge_id: uuid.UUID) -> Optional[uuid.UUID]:
        ...

    @abstractmethod
    def invoice_number(self, invoice_id: uuid.UUID) -> str:
        ...

    @abstractmethod
    def send_invoice(
        self,
        invoice_id: uuid.UUID,
        recipient_email: str,
        *,
        email_context: Optional[dict] = None,
        email_template_code: Optional[str] = None,
    ) -> None:
        ...


class IOnboardingRegistrationPort(ABC):

    @abstractmethod
    def get(self, registration_id: uuid.UUID):
        ...

    @abstractmethod
    def save_promotion_apply(self, registration_id, *, serial: str, promotion_preview: dict) -> None:
        ...


class IPaymentMethodCreatorPort(ABC):

    @abstractmethod
    def create_from_onboarding(self, *, company_id: uuid.UUID, payment_data: dict) -> uuid.UUID:
        ...


class INotificationPort(ABC):

    @abstractmethod
    def send_email(self, *, template_code: str, to: list[str], context: dict) -> bool:
        ...


class IBillingDirectoryPort(ABC):

    @abstractmethod
    def admin_of(self, company_id: uuid.UUID) -> Optional[AdminSnapshot]:
        """The company's admin as an ORM-free snapshot, or None."""
        ...

    @abstractmethod
    def company_name(self, company_id: uuid.UUID) -> str:
        ...
