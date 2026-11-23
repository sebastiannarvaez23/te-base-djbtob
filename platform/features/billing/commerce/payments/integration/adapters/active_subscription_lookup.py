"""ORM adapter: the active billing period of a company (or None).

Keeps ``CompanySubscription`` ORM out of ``invoice_billing`` / charge use cases.
Returns :class:`ActivePeriodSchema` via the subscription port.
"""

import uuid
from typing import Optional

from platform.features.billing.subscription.subscription.domain.schemas import ActivePeriodSchema
from platform.features.billing.subscription.subscription.infrastructure.active_period import (
    DjangoActivePeriodLookup,
)


def get_active_company_subscription(company_id: uuid.UUID) -> Optional[ActivePeriodSchema]:
    return DjangoActivePeriodLookup().get(company_id)
