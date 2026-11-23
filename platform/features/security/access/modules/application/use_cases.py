import uuid
from typing import List, Optional

from core.errors import AppErrorCode, ConflictException
from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.functionalities.domain.offering import apply_commercial
from platform.features.security.access.modules.domain.interfaces import IModuleRepository
from platform.features.security.access.modules.domain.schemas import (
    ModuleSchema,
    CreateModuleSchema,
    UpdateModuleSchema,
)
from core.trace import trace_layer


def _confirm_catalog_service(service_id) -> None:
    if service_id is None:
        return
    from platform.features.billing.subscription.subscription.infrastructure.neurana_catalog import (
        require_active_service,
    )
    require_active_service(service_id)


def _assert_module_offering_change_allowed(module_id: uuid.UUID, module_code: str) -> None:
    from platform.features.billing.complement.entitlement.models import CompanyComplement
    from platform.features.billing.subscription.subscription.models import SubscriptionModule

    on_plan = SubscriptionModule.objects.filter(module_code=module_code).exists()
    licensed = CompanyComplement.objects.filter(
        module_id=module_id,
        status=CompanyComplement.Status.ACTIVE,
    ).exists()
    if on_plan or licensed:
        raise ConflictException(
            AppErrorCode.CMP_OFFERING_LOCKED,
            override_detail='The offering cannot change while the module is on a plan or has an active company license.',
        )


class ListModulesUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[ModuleSchema]:
        return self.repository.get_all(filters=filters)


class ListModulesPaginatedUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class GetModuleUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID) -> Optional[ModuleSchema]:
        return self.repository.get_by_id(module_id)


class CreateModuleUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateModuleSchema) -> ModuleSchema:
        offering, billing_mode, service_id = apply_commercial(
            data.offering, data.billing_mode, data.catalog_service_id,
        )
        _confirm_catalog_service(service_id)
        if (data.offering, data.billing_mode, data.catalog_service_id) != (offering, billing_mode, service_id):
            data = data.model_copy(update={
                'offering': offering,
                'billing_mode': billing_mode,
                'catalog_service_id': service_id,
            })
        return self.repository.create(data)


class UpdateModuleUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID, data: UpdateModuleSchema) -> Optional[ModuleSchema]:
        if data.offering is not None or data.billing_mode is not None or 'catalog_service_id' in data.model_fields_set:
            current = self.repository.get_by_id(module_id)
            if current is None:
                return None
            offering = data.offering if data.offering is not None else current.offering
            billing_mode = data.billing_mode if data.billing_mode is not None else current.billing_mode
            service_id = (
                data.catalog_service_id
                if 'catalog_service_id' in data.model_fields_set
                else current.catalog_service_id
            )
            if offering != current.offering:
                _assert_module_offering_change_allowed(module_id, current.code)
            resolved_offering, resolved_billing, resolved_service = apply_commercial(
                offering, billing_mode, service_id,
            )
            _confirm_catalog_service(resolved_service)
            if (data.offering, data.billing_mode, service_id) != (
                resolved_offering, resolved_billing, resolved_service,
            ):
                data = data.model_copy(update={
                    'offering': resolved_offering,
                    'billing_mode': resolved_billing,
                    'catalog_service_id': resolved_service,
                })
        return self.repository.update(module_id, data)


class DeleteModuleUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID) -> bool:
        return self.repository.delete(module_id)


class ToggleModuleUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID) -> Optional[ModuleSchema]:
        return self.repository.toggle(module_id)


class ReorderModulesUseCase:
    def __init__(self, repository: IModuleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, ids: list[uuid.UUID]) -> int:
        return self.repository.reorder(ids)
