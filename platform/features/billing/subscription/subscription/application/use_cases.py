import uuid
from decimal import Decimal
from typing import Optional, List
from ..domain.interfaces import ISubscriptionRepository
from ..domain.schemas import (
    BillingSettingsSchema,
    CompanySubscriptionResultSchema,
    CreateSubscriptionSchema,
    PendingChangeSchema,
    SubscriptionSchema,
    UpdateSubscriptionSchema,
)
from core.trace import trace_layer


class GetAllSubscriptionsUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[SubscriptionSchema]:
        return self.repository.get_all(filters=filters)


class GetActiveSubscriptionsUseCase:
    """Public catalog: returns only ``is_active=True`` plans, cheap → expensive.

    Distinct from ``GetAllSubscriptionsUseCase``: the latter feeds the
    admin CRUD which must also see deactivated plans (to reactivate
    them). This one is consumed by anonymous traffic (onboarding wizard,
    marketing pages) where deactivated plans must never be advertised.
    """

    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> List[SubscriptionSchema]:
        return self.repository.get_active()


class GetSubscriptionByCodeUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, code: str) -> Optional[SubscriptionSchema]:
        return self.repository.get_by_code(code)


class CreateSubscriptionUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateSubscriptionSchema) -> SubscriptionSchema:
        return self.repository.create(data)


class UpdateSubscriptionUseCase:
    def __init__(self, repository: ISubscriptionRepository, catalog_services=None):
        self.repository = repository
        self.catalog_services = catalog_services

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateSubscriptionSchema) -> Optional[SubscriptionSchema]:
        service_id = getattr(data, 'catalog_service_id', None)
        fields_set = getattr(data, 'model_fields_set', set())
        if service_id and 'catalog_service_id' in fields_set:
            lookup = self.catalog_services
            if lookup is None:
                from ..infrastructure.neurana_catalog import require_active_service
                lookup = require_active_service
            service = lookup(service_id)
            data = data.model_copy(update={
                'price': service['min_billing_base'],
                'currency': service['currency'],
                'catalog_service_code': str(service.get('code') or '')[:64],
                'catalog_service_name': str(service.get('name') or '')[:255],
            })
        return self.repository.update(id, data)


class DeleteSubscriptionUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)


class CancelSubscriptionUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        return self.repository.cancel(company_id)


class ReactivateSubscriptionUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID) -> Optional[CompanySubscriptionResultSchema]:
        return self.repository.reactivate(company_id)


class GetSubscriptionChangeStatusUseCase:
    """Drives the settings UI: can the company change plan, and what change is
    currently in flight (a pending downgrade)."""

    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID) -> dict:
        pending = self.repository.get_pending_change(company_id)
        if pending is not None:
            if not isinstance(pending, PendingChangeSchema):
                pending = PendingChangeSchema.model_validate(pending)
            pending = {
                'type': pending.type,
                'from_plan': pending.from_plan,
                'to_plan': pending.to_plan,
                'activates_on': pending.activates_on.strftime('%d/%m/%Y'),
                'billing_interval': pending.billing_interval,
            }
        return {'can_change': pending is None, 'pending_change': pending}


class GetAnnualDiscountUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> BillingSettingsSchema:
        return BillingSettingsSchema(
            annual_discount_percent=self.repository.get_annual_discount_percent(),
        )


class UpdateAnnualDiscountUseCase:
    def __init__(self, repository: ISubscriptionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, percent: Decimal) -> BillingSettingsSchema:
        saved = self.repository.update_annual_discount_percent(percent)
        return BillingSettingsSchema(annual_discount_percent=saved)
