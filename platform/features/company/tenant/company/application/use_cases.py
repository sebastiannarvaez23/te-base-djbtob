from typing import Optional
from uuid import UUID

from core.errors import AppErrorCode, ConflictException
from core.query.core import PaginatedQuery, PaginatedResult
from ..domain.interfaces import ICompanyRepository
from ..domain.lifecycle import CLOSED_LIFECYCLES
from ..domain.schemas import (
    CompanyDetailSchema,
    CompanySchema,
    CompanyListItemSchema,
    CreateCompanySchema,
    UpdateCompanySchema,
)
from core.trace import trace_layer


class ListCompaniesPaginatedUseCase:
    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class GetCompanyByNitUseCase:
    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, nit: str) -> Optional[CompanySchema]:
        return self.repository.get_by_nit(nit)


class GetCompanyDetailByNitUseCase:
    """Detail with primary domain, creation date and latest subscription —
    backs the client settings 'company' screen."""

    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, nit: str) -> Optional[CompanyDetailSchema]:
        return self.repository.get_detail_by_nit(nit)


class GetCompanyDetailByIdUseCase:
    """Same detail payload as NIT lookup, keyed by company id so tenants
    without a tax id can still load settings."""

    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID) -> Optional[CompanyDetailSchema]:
        return self.repository.get_detail_by_id(company_id)


class UpdateCompanySettingsUseCase:
    """Tenant-facing company profile: name, address, and NIT only while empty."""

    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID, data: UpdateCompanySchema) -> Optional[CompanyDetailSchema]:
        current = self.repository.get_by_id(company_id)
        if current is None:
            return None

        incoming_nit = (data.nit or '').strip() if data.nit is not None else None
        existing_nit = (current.nit or '').strip()
        if incoming_nit is not None and existing_nit:
            data = data.model_copy(update={'nit': None})
        elif incoming_nit:
            taken = self.repository.get_by_nit(incoming_nit)
            if taken and taken.id != company_id:
                raise ConflictException(AppErrorCode.COMPANY_DUPLICATE_NIT)

        updated = self.repository.update_settings(company_id, data)
        if updated is not None:
            from platform.features.company.tenant.company.application.neurana_customer import (
                register_company_customer,
            )

            register_company_customer(updated.id)
        return updated


class CreateCompanyUseCase:
    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCompanySchema) -> CompanySchema:
        from platform.features.company.tenant.company.application.geo_city import (
            assert_active_geo_city,
        )

        assert_active_geo_city(data.geo_city_id)
        created = self.repository.create(data)
        if created is not None and created.id is not None:
            from platform.features.company.tenant.company.application.neurana_customer import (
                register_company_customer,
            )

            register_company_customer(created.id)
        return created


class ToggleCompanyActiveUseCase:
    def __init__(self, repository: ICompanyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID) -> Optional[CompanyListItemSchema]:
        current = self.repository.get_by_id(company_id)
        if current is None:
            return None
        if current.lifecycle in CLOSED_LIFECYCLES:
            raise ConflictException(AppErrorCode.COMPANY_ALREADY_CLOSED)
        return self.repository.toggle_active(company_id)
