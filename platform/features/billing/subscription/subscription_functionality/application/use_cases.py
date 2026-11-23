import uuid
from typing import List, Optional
from ..domain.interfaces import ISubscriptionFunctionalityRepository
from ..domain.schemas import SubscriptionFunctionalitySchema, UpdateSubscriptionFunctionalitiesSchema
from core.errors import AppErrorCode, ConflictException
from core.trace import trace_layer


def _reject_complement_keys(keys: list[str]) -> None:
    if not keys:
        return
    from platform.features.security.access.functionalities.models import Functionality

    blocked = Functionality.objects.filter(
        key__in=keys,
        offering=Functionality.Offering.COMPLEMENT,
    ).exists()
    if blocked:
        raise ConflictException(
            AppErrorCode.CMP_NOT_ON_PLAN,
            override_detail='This functionality is sold as a complement and cannot be included in a subscription plan.',
        )


class GetSubscriptionFunctionalitiesUseCase:
    def __init__(self, repository: ISubscriptionFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionFunctionalitySchema]:
        return self.repository.get_by_subscription(subscription_id, filters=filters)


class UpdateSubscriptionFunctionalitiesUseCase:
    def __init__(self, repository: ISubscriptionFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, subscription_id: uuid.UUID, data: UpdateSubscriptionFunctionalitiesSchema) -> Optional[List[SubscriptionFunctionalitySchema]]:
        _reject_complement_keys(data.functionality_keys)
        return self.repository.update_functionalities(subscription_id, data)
