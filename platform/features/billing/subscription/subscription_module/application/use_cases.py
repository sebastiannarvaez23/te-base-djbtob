import uuid
from typing import List, Optional
from ..domain.interfaces import ISubscriptionModuleRepository
from ..domain.schemas import SubscriptionModuleSchema, UpdateSubscriptionModulesSchema
from core.errors import AppErrorCode, ConflictException
from core.trace import trace_layer
from platform.features.security.access.modules.models import Module


class GetSubscriptionModulesUseCase:
    def __init__(self, repository: ISubscriptionModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionModuleSchema]:
        return self.repository.get_by_subscription(subscription_id, filters=filters)


class UpdateSubscriptionModulesUseCase:
    def __init__(self, repository: ISubscriptionModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, subscription_id: uuid.UUID, data: UpdateSubscriptionModulesSchema) -> Optional[List[SubscriptionModuleSchema]]:
        _reject_complement_modules(data.module_codes)
        return self.repository.update_modules(subscription_id, data)


def _reject_complement_modules(codes: list[str]) -> None:
    if not codes:
        return
    blocked = Module.objects.filter(code__in=codes, offering='complement').exists()
    if blocked:
        raise ConflictException(
            AppErrorCode.CMP_NOT_ON_PLAN,
            override_detail='This module is sold as a complement and cannot be included in a subscription plan.',
        )
