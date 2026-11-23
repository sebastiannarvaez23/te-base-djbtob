"""Casos de uso del lado público (admin outbox + resource types).

Un caso de uso = una responsabilidad = un ``execute()``. Reciben puertos
por constructor (DIP); ninguna lógica de infraestructura vive aquí.
"""

import logging
import uuid

from django.db import transaction

from core.errors.codes import AppErrorCode
from core.errors.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.query.core import PaginatedQuery, PaginatedResult
from core.realtime.envelope import RealtimeMessage
from core.realtime.publisher import IRealtimePublisher

from platform.features.communication.messaging.inbox.domain.enums import AudienceScope, ReadStatus
from platform.features.communication.messaging.inbox.domain.interfaces import (
    IAudienceResolver,
    IOutboxDispatchTrigger,
    IOutboxRepository,
    IResourceTypeRepository,
    IAdminInboxRepository,
)
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminInboxPayload,
    AdminNotifyInput,
    CreateResourceTypeSchema,
    OutboxItem,
    ResourceTypeSchema,
    UpdateResourceTypeSchema,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


# ── Envío del administrador ───────────────────────────────────────────────────

class CreateAdminNotificationUseCase:
    """Registra el envío del admin (outbox) y dispara el fan-out asíncrono."""

    def __init__(self, outbox_repo: IOutboxRepository, dispatch_trigger: IOutboxDispatchTrigger):
        self.outbox_repo = outbox_repo
        self.dispatch_trigger = dispatch_trigger

    @trace_layer('application')
    def execute(self, data: AdminNotifyInput) -> OutboxItem:
        self._validate_audience(data)
        item = self.outbox_repo.create(data)
        self.dispatch_trigger.trigger(item.id)
        return item

    @staticmethod
    def _validate_audience(data: AdminNotifyInput) -> None:
        scope = data.audience.scope
        if scope == AudienceScope.SINGLE_USER and not data.audience.target_user_id:
            raise ValidationAppException(
                AppErrorCode.NOTIF_INVALID_AUDIENCE,
                override_detail='SINGLE_USER scope requires target_user_id.',
            )
        if scope == AudienceScope.COMPANY_USERS and not data.audience.target_company_id:
            raise ValidationAppException(
                AppErrorCode.NOTIF_INVALID_AUDIENCE,
                override_detail='COMPANY_USERS scope requires target_company_id.',
            )


class ListAdminOutboxUseCase:
    def __init__(self, outbox_repo: IOutboxRepository):
        self.outbox_repo = outbox_repo

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.outbox_repo.get_paginated(query)


# ── Tipos de recurso compartible ──────────────────────────────────────────────

class ListResourceTypesUseCase:
    def __init__(self, repository: IResourceTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, only_active: bool = False) -> list[ResourceTypeSchema]:
        return self.repository.list(only_active=only_active)


class CreateResourceTypeUseCase:
    def __init__(self, repository: IResourceTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateResourceTypeSchema) -> ResourceTypeSchema:
        if self.repository.get_by_code(data.code) is not None:
            raise ConflictException(AppErrorCode.NOTIF_RESOURCE_TYPE_DUPLICATE)
        return self.repository.create(data)


class UpdateResourceTypeUseCase:
    def __init__(self, repository: IResourceTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, code: str, data: UpdateResourceTypeSchema) -> ResourceTypeSchema:
        result = self.repository.update(code, data)
        if result is None:
            raise NotFoundException(AppErrorCode.NOTIF_RESOURCE_TYPE_NOT_FOUND)
        return result


# ── Campanita del portal admin ────────────────────────────────────────────────

class ListAdminInboxUseCase:
    def __init__(self, repository: IAdminInboxRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id, status: ReadStatus, limit: int, offset: int):
        return self.repository.list_for_user(user_id, status, limit, offset)


class GetAdminInboxUnreadCountUseCase:
    def __init__(self, repository: IAdminInboxRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id) -> int:
        return self.repository.unread_count(user_id)


class MarkAdminInboxReadUseCase:
    def __init__(self, repository: IAdminInboxRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id, recipient_id) -> int:
        return self.repository.mark_read(user_id, recipient_id)


class MarkAllAdminInboxReadUseCase:
    def __init__(self, repository: IAdminInboxRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id) -> int:
        return self.repository.mark_read(user_id, None)


class ArchiveAdminInboxUseCase:
    def __init__(self, repository: IAdminInboxRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id, recipient_id) -> int:
        return self.repository.archive(user_id, recipient_id)


class DeliverAdminInboxUseCase:
    """Materializa una notificación y la empuja en vivo a cada AdminUser."""

    def __init__(self, repository: IAdminInboxRepository, publisher: IRealtimePublisher):
        self.repository = repository
        self.publisher = publisher

    @trace_layer('application')
    def execute(self, payload: AdminInboxPayload, user_ids: list) -> int:
        ids = list(dict.fromkeys(user_ids))
        if not ids:
            return 0

        with transaction.atomic():
            notification_id = self.repository.create_notification(payload)
            count = self.repository.add_recipients(notification_id, ids)

        message = RealtimeMessage(
            type='notification.new',
            payload={
                'notification_id': str(notification_id),
                'kind': payload.kind,
                'title': payload.title,
                'body': payload.body,
                'level': payload.level.value,
                'actor_label': payload.actor_label,
                'resource_type_code': payload.resource_type_code,
                'resource_id': str(payload.resource_id) if payload.resource_id else None,
                'resource_route': payload.resource_route,
            },
        )
        for user_id in ids:
            try:
                self.publisher.to_user('public', user_id, message)
            except Exception:
                logger.exception(
                    'admin_inbox_realtime_push_failed notification_id=%s user_id=%s',
                    notification_id,
                    user_id,
                )
        return count
