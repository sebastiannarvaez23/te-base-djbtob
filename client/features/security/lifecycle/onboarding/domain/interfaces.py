from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from uuid import UUID

from .schemas import (
    AdminUserStepSchema,
    CompanyStepSchema,
    OnboardingPlanQuote,
    PaymentStepSchema,
    SubscriptionStepSchema,
)


class ICompanyRegistrationRepository(ABC):
    """Persistence port for onboarding state."""

    @abstractmethod
    def create(self, email: str, ttl_seconds: int) -> "CompanyRegistrationOrm":  # noqa: F821
        ...

    @abstractmethod
    def get(self, registration_id: UUID) -> Optional["CompanyRegistrationOrm"]:  # noqa: F821
        ...

    @abstractmethod
    def get_active_by_email(self, email: str) -> Optional["CompanyRegistrationOrm"]:  # noqa: F821
        ...

    @abstractmethod
    def save_company_step(self, registration_id: UUID, data: CompanyStepSchema, schema_name: str) -> None:
        ...

    @abstractmethod
    def username_taken(self, username: str) -> bool:
        ...

    @abstractmethod
    def email_taken(self, email: str) -> bool:
        ...

    @abstractmethod
    def provision_admin_user(self, company_id: UUID, user_data: dict) -> UUID:
        ...

    @abstractmethod
    def save_admin_user_step(self, registration_id: UUID, data: AdminUserStepSchema, hashed_password: str) -> None:
        ...

    @abstractmethod
    def save_subscription_step(
        self,
        registration_id: UUID,
        data: SubscriptionStepSchema,
        requires_payment: bool,
        subscription_payload: dict,
    ) -> None:
        ...

    @abstractmethod
    def save_payment_step(self, registration_id: UUID, data: PaymentStepSchema) -> None:
        ...

    @abstractmethod
    def lock_for_finalize(self, registration_id: UUID) -> "CompanyRegistrationOrm":  # noqa: F821
        ...

    @abstractmethod
    def mark_completed(self, registration_id: UUID, company_id: UUID) -> None:
        ...

    @abstractmethod
    def mark_failed_provisioning(self, registration_id: UUID, reason: str) -> None:
        ...

    @abstractmethod
    def save_promotion_apply(
        self,
        registration_id: UUID,
        *,
        serial: str,
        promotion_preview: dict,
    ) -> None:
        ...


class IOnboardingTokenStore(ABC):
    """Short-lived token → registration_id mapping (Redis)."""

    @abstractmethod
    def issue(self, registration_id: UUID, ttl_seconds: int) -> str:
        ...

    @abstractmethod
    def resolve(self, token: str) -> Optional[UUID]:
        ...

    @abstractmethod
    def revoke(self, token: str) -> None:
        ...


class IOnboardingResumeTokenStore(ABC):
    """Long-lived magic-link token → registration_id mapping.

    Distinct from the session token store: lifetime matches the
    registration TTL (days, not hours) and tokens are sent over email,
    so they live in a separate Redis namespace to prevent cross-use.
    """

    @abstractmethod
    def issue(self, registration_id: UUID, ttl_seconds: int) -> str:
        ...

    @abstractmethod
    def resolve(self, token: str) -> Optional[UUID]:
        ...

    @abstractmethod
    def revoke(self, token: str) -> None:
        ...


class IResumeLinkThrottle(ABC):
    """Per-email slot for resume-link re-sends (SET NX)."""

    @abstractmethod
    def try_acquire(self, email: str) -> bool:
        ...

    @abstractmethod
    def retry_after(self, email: str) -> Optional[int]:
        ...


class IOnboardingPlanCatalog(ABC):
    """Port: catálogo de planes activos para el paso de suscripción."""

    @abstractmethod
    def get_active_plan(self, subscription_id: UUID) -> Optional[OnboardingPlanQuote]:
        ...

    @abstractmethod
    def annual_discount_percent(self) -> Decimal:
        ...


class IFinalizeSideEffects(ABC):
    """Post-commit onboarding hooks (billing, welcome mail, inbox)."""

    @abstractmethod
    def after_commit(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        registration_id: UUID,
        email_confirm_required: bool,
    ) -> None:
        ...
