import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import SubscriptionFunctionalitySchema, UpdateSubscriptionFunctionalitiesSchema


class ISubscriptionFunctionalityRepository(ABC):

    @abstractmethod
    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionFunctionalitySchema]:
        ...

    @abstractmethod
    def update_functionalities(self, subscription_id: uuid.UUID, data: UpdateSubscriptionFunctionalitiesSchema) -> Optional[List[SubscriptionFunctionalitySchema]]:
        ...
