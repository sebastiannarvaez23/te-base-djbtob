import uuid
from abc import ABC, abstractmethod
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult

from platform.features.billing.complement.entitlement.domain.schemas import (
    CompanyComplementSchema,
    ComplementFunctionalitySchema,
    GrantComplementSchema,
)


class ICompanyComplementRepository(ABC):

    @abstractmethod
    def company_exists(self, company_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def get_grantable(self, functionality_id: uuid.UUID) -> Optional[ComplementFunctionalitySchema]: ...

    def get_grantable_module(self, module_id: uuid.UUID) -> Optional[ComplementFunctionalitySchema]: ...

    @abstractmethod
    def create_active(self, data: GrantComplementSchema, billing_mode: str) -> CompanyComplementSchema: ...

    @abstractmethod
    def get_for_company(
        self, company_id: uuid.UUID, entitlement_id: uuid.UUID, *, lock: bool = False,
    ) -> Optional[CompanyComplementSchema]: ...

    @abstractmethod
    def mark_revoked(self, entitlement_id: uuid.UUID, notes: str) -> CompanyComplementSchema: ...

    @abstractmethod
    def list_catalog(self, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def list_for_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult: ...
