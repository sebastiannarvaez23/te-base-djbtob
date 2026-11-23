"""
Billing directory — a single read port for the cross-feature lookups the
billing use cases need (the company's admin user, the company, its active
payment method, a plan's name).

Before this, each use case duplicated these ORM queries inline (``_load_admin``
etc. in 4 files), mixing data access into the application layer. Now the use
cases depend on this port and stay ORM-free; ``DjangoBillingDirectory`` is the
single Django adapter, and tests inject a fake.
"""
import uuid
from abc import ABC, abstractmethod
from typing import Optional

_ADMIN_ROLE_NAME = 'Administrator'


class IBillingDirectory(ABC):

    @abstractmethod
    def admin_of(self, company_id: uuid.UUID):
        """The company's admin user (role 'Administrator'), or None."""
        ...

    @abstractmethod
    def company(self, company_id: uuid.UUID):
        """The Company (tenant), or None."""
        ...

    @abstractmethod
    def active_card(self, company_id: uuid.UUID):
        """The company's most recent active payment method, or None."""
        ...

    @abstractmethod
    def subscription_name(self, subscription_id: uuid.UUID) -> Optional[str]:
        """A plan's name, or None."""
        ...


class DjangoBillingDirectory(IBillingDirectory):
    """Django/ORM adapter. Deferred imports avoid app-load cycles."""

    def admin_of(self, company_id):
        from client.features.security.lifecycle.registration.models import User
        return (
            User.objects
            .filter(company_id=company_id, rol__name=_ADMIN_ROLE_NAME, is_active=True)
            .order_by('id')
            .first()
        )

    def company(self, company_id):
        from platform.features.company.tenant.company.models import Company
        return Company.objects.filter(id=company_id).first()

    def active_card(self, company_id):
        from platform.features.billing.commerce.payment_method.models import PaymentMethod
        return (
            PaymentMethod.objects
            .filter(company_id=company_id, is_active=True)
            .order_by('-created_at')
            .first()
        )

    def subscription_name(self, subscription_id) -> Optional[str]:
        from platform.features.billing.subscription.subscription.models import Subscription
        return (
            Subscription.objects
            .filter(id=subscription_id)
            .values_list('name', flat=True)
            .first()
        )
