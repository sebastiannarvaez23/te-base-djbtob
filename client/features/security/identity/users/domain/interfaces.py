from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from client.features.security.identity.users.domain.schemas import (
    CompanyUserSchema,
    CreateCompanyUserSchema,
    UpdateCompanyUserSchema,
)


class ICompanyUserRepository(ABC):
    @abstractmethod
    def list(
        self,
        company_id: UUID,
        filters: dict,
        offset: int,
        limit: int,
    ) -> tuple[list[CompanyUserSchema], int]: ...

    @abstractmethod
    def create(self, data: CreateCompanyUserSchema) -> CompanyUserSchema: ...

    @abstractmethod
    def get_by_id(self, user_id: UUID, company_id: UUID) -> Optional[CompanyUserSchema]: ...

    @abstractmethod
    def update(
        self,
        user_id: UUID,
        company_id: UUID,
        data: UpdateCompanyUserSchema,
    ) -> Optional[CompanyUserSchema]: ...

    @abstractmethod
    def toggle_active(self, user_id: UUID, company_id: UUID) -> Optional[CompanyUserSchema]: ...
