from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult
from .schemas import TenantUserSchema


class ITenantUserRepository(ABC):

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def toggle_active(self, user_id: UUID) -> Optional[TenantUserSchema]:
        ...
