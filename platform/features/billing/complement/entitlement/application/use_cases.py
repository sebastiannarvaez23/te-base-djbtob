import uuid

from django.db import IntegrityError, transaction

from core.access.subscription import SubscriptionCache
from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from core.query.core import PaginatedQuery, PaginatedResult
from core.trace import trace_layer

from platform.features.billing.complement.entitlement.domain.interfaces import ICompanyComplementRepository
from platform.features.billing.complement.entitlement.domain.schemas import (
    CompanyComplementSchema,
    GrantComplementSchema,
    RevokeComplementSchema,
)


def _invalidate(company_id: uuid.UUID) -> None:
    SubscriptionCache.invalidate(str(company_id))


_ACTIVE_LICENSE_CONSTRAINTS = frozenset({
    'uniq_active_company_complement',
    'uniq_active_company_module_complement',
})


def _is_duplicate_active_license(exc: IntegrityError) -> bool:
    cause = getattr(exc, '__cause__', None)
    name = getattr(getattr(cause, 'diag', None), 'constraint_name', None)
    return not name or name in _ACTIVE_LICENSE_CONSTRAINTS


class ListComplementCatalogUseCase:
    def __init__(self, repository: ICompanyComplementRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.list_catalog(query)


class ListCompanyComplementsUseCase:
    def __init__(self, repository: ICompanyComplementRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        if not self.repository.company_exists(company_id):
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        return self.repository.list_for_company(company_id, query)


class GrantCompanyComplementUseCase:
    def __init__(self, repository: ICompanyComplementRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: GrantComplementSchema) -> CompanyComplementSchema:
        if not self.repository.company_exists(data.company_id):
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if data.functionality_id and data.module_id:
            raise ValidationAppException(AppErrorCode.CMP_NOT_AVAILABLE)
        if data.functionality_id:
            target = self.repository.get_grantable(data.functionality_id)
        elif data.module_id:
            target = self.repository.get_grantable_module(data.module_id)
        else:
            raise ValidationAppException(AppErrorCode.CMP_NOT_AVAILABLE)
        if target is None:
            raise ValidationAppException(AppErrorCode.CMP_NOT_AVAILABLE)
        try:
            with transaction.atomic():
                created = self.repository.create_active(data, target.billing_mode)
        except IntegrityError as exc:
            if not _is_duplicate_active_license(exc):
                raise
            raise ConflictException(AppErrorCode.CMP_ALREADY_ACTIVE) from exc
        _invalidate(data.company_id)
        return created


class RevokeCompanyComplementUseCase:
    def __init__(self, repository: ICompanyComplementRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: RevokeComplementSchema) -> CompanyComplementSchema:
        if not self.repository.company_exists(data.company_id):
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        with transaction.atomic():
            current = self.repository.get_for_company(
                data.company_id, data.entitlement_id, lock=True,
            )
            if current is None:
                raise NotFoundException(AppErrorCode.CMP_NOT_FOUND)
            if current.status != 'active':
                raise ConflictException(AppErrorCode.CMP_NOT_ACTIVE)
            revoked = self.repository.mark_revoked(data.entitlement_id, data.notes)
        _invalidate(data.company_id)
        return revoked
