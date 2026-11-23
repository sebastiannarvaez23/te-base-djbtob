import logging
import math
from typing import Optional
from uuid import UUID

from client.features.security.identity.users.domain.interfaces import ICompanyUserRepository
from client.features.security.identity.users.domain.schemas import (
    CompanyUserSchema,
    CreateCompanyUserSchema,
    UpdateCompanyUserSchema,
)
from core.access.checker import AccessChecker
from core.access.enforcement import USERS_QUOTA_FEATURE
from platform.features.company.tenant.company.models import Company
from core.trace import trace_layer

logger = logging.getLogger('app.api')


def _ensure_users_quota(company_id: UUID) -> None:
    """Gate de cupo activo. Patrón a replicar en otros dominios (ver EXTENDING.md)."""
    company = Company.objects.filter(id=company_id).first()
    if company is not None:
        AccessChecker.ensure_quota_or_raise(company, USERS_QUOTA_FEATURE)


class ListCompanyUsersUseCase:
    def __init__(self, repository: ICompanyUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        company_id: UUID,
        filters: dict,
        page: int,
        page_size: int,
        offset: int,
        limit: int,
    ) -> dict:
        items, total = self.repository.list(company_id, filters, offset, limit)
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': math.ceil(total / page_size) if total else 0,
        }


class CreateCompanyUserUseCase:
    def __init__(self, repository: ICompanyUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCompanyUserSchema) -> CompanyUserSchema:
        _ensure_users_quota(data.company_id)
        created = self.repository.create(data)
        self._notify_collaborator_welcome(data.company_id, created)
        self._send_welcome_user_email(data.company_id, created)
        return created

    @staticmethod
    def _send_welcome_user_email(company_id: UUID, created: CompanyUserSchema) -> None:
        try:
            from client.features.security.lifecycle.registration.models import User
            from platform.features.communication.notification.dispatchers import (
                dispatch_welcome_user,
            )

            company = Company.objects.filter(id=company_id).first()
            user = User.objects.filter(pk=created.id).first()
            if company is None or user is None:
                return
            dispatch_welcome_user(user=user, company=company)
        except Exception:
            logger.exception(
                'dispatch_welcome_user failed company=%s user=%s',
                company_id, created.id,
            )

    @staticmethod
    def _notify_collaborator_welcome(company_id: UUID, created: CompanyUserSchema) -> None:
        try:
            from client.features.communication.messaging.inbox.application.welcome_notifier import (
                notify_collaborator_welcome,
            )

            company = Company.objects.filter(id=company_id).only('schema_name', 'name').first()
            if company is None:
                return
            notify_collaborator_welcome(
                schema_name=company.schema_name,
                user_id=created.id,
                user_name=(
                    f'{created.first_name or ""} {created.last_name or ""}'.strip()
                    or created.username
                ),
                company_name=company.name,
            )
        except Exception:
            logger.exception(
                'notify_collaborator_welcome failed company=%s user=%s',
                company_id, created.id,
            )


class UpdateCompanyUserUseCase:
    def __init__(self, repository: ICompanyUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        user_id: UUID,
        company_id: UUID,
        data: UpdateCompanyUserSchema,
    ) -> Optional[CompanyUserSchema]:
        return self.repository.update(user_id, company_id, data)


class ToggleCompanyUserActiveUseCase:
    def __init__(self, repository: ICompanyUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: UUID, company_id: UUID) -> Optional[CompanyUserSchema]:
        existing = self.repository.get_by_id(user_id, company_id)
        if existing is None:
            return None
        if not existing.is_active:
            _ensure_users_quota(company_id)
        return self.repository.toggle_active(user_id, company_id)
