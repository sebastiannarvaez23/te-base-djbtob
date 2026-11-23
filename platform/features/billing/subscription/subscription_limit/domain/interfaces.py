import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import CreateSubscriptionLimitSchema, SubscriptionLimitSchema, UpdateSubscriptionLimitSchema


class ISubscriptionLimitRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[SubscriptionLimitSchema]:
        ...

    @abstractmethod
    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionLimitSchema]:
        ...

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[SubscriptionLimitSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateSubscriptionLimitSchema) -> SubscriptionLimitSchema:
        ...

    @abstractmethod
    def update(self, id: uuid.UUID, data: UpdateSubscriptionLimitSchema) -> Optional[SubscriptionLimitSchema]:
        ...

    @abstractmethod
    def delete(self, id: uuid.UUID) -> bool:
        ...
