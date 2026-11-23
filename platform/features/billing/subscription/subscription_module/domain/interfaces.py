import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import SubscriptionModuleSchema, UpdateSubscriptionModulesSchema


class ISubscriptionModuleRepository(ABC):

    @abstractmethod
    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionModuleSchema]:
        ...

    @abstractmethod
    def update_modules(self, subscription_id: uuid.UUID, data: UpdateSubscriptionModulesSchema) -> List[SubscriptionModuleSchema]:
        ...
