from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult
from .schemas import (
    CompanyDetailSchema,
    CompanyLifecycleRecord,
    CompanySchema,
    CompanyListItemSchema,
    CreateCompanySchema,
    UpdateCompanySchema,
)


class ICompanyRepository(ABC):

    @abstractmethod
    def get_by_nit(self, nit: str) -> Optional[CompanySchema]:
        ...

    @abstractmethod
    def get_detail_by_nit(self, nit: str) -> Optional[CompanyDetailSchema]:
        ...

    @abstractmethod
    def get_by_id(self, company_id: UUID) -> Optional[CompanySchema]:
        ...

    @abstractmethod
    def get_by_schema_name(self, schema_name: str) -> Optional[CompanySchema]:
        ...

    @abstractmethod
    def get_detail_by_id(self, company_id: UUID) -> Optional[CompanyDetailSchema]:
        ...

    @abstractmethod
    def get_all(self) -> List[CompanySchema]:
        ...

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def create(self, data: CreateCompanySchema) -> CompanySchema:
        ...

    @abstractmethod
    def toggle_active(self, company_id: UUID) -> Optional[CompanyListItemSchema]:
        ...

    @abstractmethod
    def update_settings(self, company_id: UUID, data: UpdateCompanySchema) -> Optional[CompanyDetailSchema]:
        ...


class ICompanyOffboardingRepository(ABC):
    @abstractmethod
    def get_lifecycle(self, company_id: UUID) -> Optional[CompanyLifecycleRecord]:
        ...

    @abstractmethod
    def apply_close(
        self,
        company_id: UUID,
        *,
        reason: str,
        actor_admin_id: UUID | None,
        closed_at,
        purge_after,
        spare_user_id: UUID | None = None,
    ) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def apply_close_reason(self, company_id: UUID, *, reason: str) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def deactivate_member(self, company_id: UUID, user_id: UUID) -> None:
        ...

    @abstractmethod
    def apply_reopen(self, company_id: UUID) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def apply_legal_hold(
        self,
        company_id: UUID,
        *,
        enabled: bool,
        reason: str,
    ) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def apply_export_attestation(
        self,
        company_id: UUID,
        *,
        actor_admin_id: UUID | None,
        attested_at,
        object_key: str,
    ) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def list_export_users(self, company_id: UUID) -> list[dict]:
        ...

    @abstractmethod
    def list_purge_candidates(self, *, now) -> list[CompanyLifecycleRecord]:
        ...

    @abstractmethod
    def mark_pending_purge(self, company_id: UUID) -> CompanyLifecycleRecord:
        ...

    @abstractmethod
    def apply_purge(
        self,
        company_id: UUID,
        *,
        now,
        dry_run: bool,
    ) -> CompanyLifecycleRecord:
        ...


class ITenantSessionRevoker(ABC):
    @abstractmethod
    def revoke_all(self, user_ids: list[UUID]) -> int:
        ...


class ICompanyCloseNotifier(ABC):
    @abstractmethod
    def notify_closed(self, record: CompanyLifecycleRecord) -> None:
        ...


class ITenantExportStore(ABC):
    @abstractmethod
    def put_json(self, schema_name: str, payload: bytes) -> str:
        ...

    @abstractmethod
    def presign(self, object_key: str):
        ...

    @abstractmethod
    def delete_tenant_prefix(self, schema_name: str) -> int:
        ...
