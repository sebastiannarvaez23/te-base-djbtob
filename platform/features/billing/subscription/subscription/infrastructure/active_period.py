import uuid
from typing import Optional

from ..domain.interfaces import IActivePeriodLookup
from ..domain.schemas import ActivePeriodSchema
from ..models import CompanySubscription


class DjangoActivePeriodLookup(IActivePeriodLookup):
    """Reads the live billing period without leaking ORM to other features."""

    def get(self, company_id: uuid.UUID) -> Optional[ActivePeriodSchema]:
        cs = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .order_by('-start_date')
            .only('id', 'subscription_id', 'status')
            .first()
        )
        if cs is None:
            return None
        return ActivePeriodSchema(
            id=cs.id,
            subscription_id=cs.subscription_id,
            status=cs.status,
        )
