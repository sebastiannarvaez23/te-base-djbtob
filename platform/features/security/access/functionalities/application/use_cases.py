import uuid
from typing import Optional

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException, ValidationAppException
from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.functionalities.domain.interfaces import IFunctionalityRepository
from platform.features.security.access.functionalities.domain.offering import apply_commercial, offering_pairing_ok
from platform.features.security.access.functionalities.domain.schemas import (
    AssignFunctionalitySchema,
    CreateFunctionalitySchema,
    FunctionalitySchema,
    UpdateFunctionalitySchema,
)


from platform.features.security.access.functionalities.models import Functionality
from core.trace import trace_layer


def _confirm_catalog_service(service_id) -> None:
    if service_id is None:
        return
    from platform.features.billing.subscription.subscription.infrastructure.neurana_catalog import (
        require_active_service,
    )
    require_active_service(service_id)


def _assert_offering_pairing(offering: str, billing_mode: str) -> None:
    if offering_pairing_ok(offering, billing_mode):
        return
    raise ValidationAppException(
        AppErrorCode.CMP_OFFERING_MISMATCH,
        override_detail='A plan item is included. A complement is added to the subscription or paid once.',
    )


def _assert_offering_change_allowed(functionality_id: uuid.UUID) -> None:
    from platform.features.billing.complement.entitlement.models import CompanyComplement
    from platform.features.billing.subscription.subscription.models import SubscriptionFunctionality

    on_plan = SubscriptionFunctionality.objects.filter(functionality_id=functionality_id).exists()
    licensed = CompanyComplement.objects.filter(
        functionality_id=functionality_id,
        status=CompanyComplement.Status.ACTIVE,
    ).exists()
    if on_plan or licensed:
        raise ConflictException(
            AppErrorCode.CMP_OFFERING_LOCKED,
            override_detail='The offering cannot change while the functionality is on a plan or has an active company license.',
        )


def _ensure_unique_functionality_key(key: str, exclude_id: Optional[uuid.UUID] = None) -> None:
    qs = Functionality.objects.filter(key=key)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.FUNC_DUPLICATE_KEY,
            override_detail=f"A functionality with key '{key}' already exists.",
        )


class ListFunctionalitiesPaginatedUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class GetFunctionalityUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]:
        return self.repository.get_by_id(functionality_id)


class CreateFunctionalityUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateFunctionalitySchema) -> FunctionalitySchema:
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
        _ensure_unique_functionality_key(data.key)
        try:
            return self.repository.create(data)
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.FUNC_DUPLICATE_KEY,
                override_detail=f"A functionality with key '{data.key}' already exists.",
            )


class UpdateFunctionalityUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, functionality_id: uuid.UUID, data: UpdateFunctionalitySchema) -> Optional[FunctionalitySchema]:
        if data.key is not None:
            _ensure_unique_functionality_key(data.key, exclude_id=functionality_id)
        if data.offering is not None or data.billing_mode is not None or 'catalog_service_id' in data.model_fields_set:
            current = self.repository.get_by_id(functionality_id)
            if current is None:
                return None
            offering = data.offering if data.offering is not None else current.offering
            billing_mode = data.billing_mode if data.billing_mode is not None else current.billing_mode
            service_id = (
                data.catalog_service_id
                if 'catalog_service_id' in data.model_fields_set
                else current.catalog_service_id
            )
            _assert_offering_pairing(offering, billing_mode)
            if offering != current.offering:
                _assert_offering_change_allowed(functionality_id)
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
        try:
            return self.repository.update(functionality_id, data)
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.FUNC_DUPLICATE_KEY,
                override_detail=f"A functionality with key '{data.key}' already exists.",
            )


class DeleteFunctionalityUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, functionality_id: uuid.UUID) -> bool:
        return self.repository.delete(functionality_id)


class ToggleFunctionalityUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]:
        return self.repository.toggle(functionality_id)


class AssignFunctionalityToModuleUseCase:
    def __init__(self, repository: IFunctionalityRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, functionality_id: uuid.UUID, data: AssignFunctionalitySchema) -> Optional[FunctionalitySchema]:
        return self.repository.assign_module(functionality_id, data)
