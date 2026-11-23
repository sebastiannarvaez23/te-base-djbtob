"""Puertos del dominio público de notificaciones (DIP + ISP).

Puertos pequeños y cohesivos:
  - IOutboxRepository      → persistencia del registro de envíos admin.
  - IResourceTypeRepository→ registro de tipos compartibles.
  - IAudienceResolver      → traduce una Audience a grupos por schema.
"""

import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from core.query.core import PaginatedQuery, PaginatedResult

from platform.features.communication.messaging.inbox.domain.enums import OutboxStatus, ReadStatus
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminInboxItem,
    AdminInboxPayload,
    AdminNotifyInput,
    Audience,
    CreateResourceTypeSchema,
    OutboxItem,
    RecipientGroup,
    ResourceTypeSchema,
    UpdateResourceTypeSchema,
)


class IOutboxRepository(ABC):
    """Port: persiste y consulta la bandeja de salida del administrador."""

    @abstractmethod
    def create(self, data: AdminNotifyInput) -> OutboxItem:
        ...

    @abstractmethod
    def get(self, outbox_id: uuid.UUID) -> Optional[OutboxItem]:
        ...

    @abstractmethod
    def set_status(
        self,
        outbox_id: uuid.UUID,
        status: OutboxStatus,
        recipients_count: Optional[int] = None,
        error_detail: str = '',
    ) -> None:
        ...

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...


class IResourceTypeRepository(ABC):
    """Port: registro configurable de tipos de recurso compartible."""

    @abstractmethod
    def list(self, only_active: bool = False) -> List[ResourceTypeSchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[ResourceTypeSchema]:
        ...

    @abstractmethod
    def create(self, data: CreateResourceTypeSchema) -> ResourceTypeSchema:
        ...

    @abstractmethod
    def update(self, code: str, data: UpdateResourceTypeSchema) -> Optional[ResourceTypeSchema]:
        ...


class IAudienceResolver(ABC):
    """Port (Strategy): resuelve una Audience a destinatarios por schema."""

    @abstractmethod
    def resolve(self, audience: Audience) -> List[RecipientGroup]:
        ...


class IOutboxDispatchTrigger(ABC):
    """Port: dispara el fan-out de un outbox ya creado.

    Desacopla la plataforma del mundo tenant: la implementación encola una
    tarea Celery por NOMBRE, sin importar código de ``client``.
    """

    @abstractmethod
    def trigger(self, outbox_id: uuid.UUID) -> None:
        ...


class IAdminInboxRepository(ABC):
    """Port: campanita persistida en schema público para AdminUser."""

    @abstractmethod
    def create_notification(self, payload: AdminInboxPayload) -> uuid.UUID:
        ...

    @abstractmethod
    def add_recipients(self, notification_id: uuid.UUID, user_ids: List[uuid.UUID]) -> int:
        ...

    @abstractmethod
    def list_for_user(
        self,
        user_id: uuid.UUID,
        status: ReadStatus,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminInboxItem], int]:
        ...

    @abstractmethod
    def unread_count(self, user_id: uuid.UUID) -> int:
        ...

    @abstractmethod
    def mark_read(self, user_id: uuid.UUID, recipient_id: Optional[uuid.UUID]) -> int:
        ...

    @abstractmethod
    def archive(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        ...


class IAdminFeatureAudienceLookup(ABC):
    """Port: AdminUsers cuyo rol tiene una feature del catálogo admin."""

    @abstractmethod
    def user_ids_for_feature(self, feature_key: str) -> List[uuid.UUID]:
        ...
