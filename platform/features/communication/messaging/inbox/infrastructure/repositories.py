"""Adaptadores ORM del lado público (outbox + resource types)."""

import uuid
from typing import List, Optional

from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult

from platform.features.communication.messaging.inbox.domain.enums import (
    NotificationLevel,
    OutboxStatus,
    ReadStatus,
)
from platform.features.communication.messaging.inbox.domain.interfaces import (
    IAdminFeatureAudienceLookup,
    IAdminInboxRepository,
    IOutboxRepository,
    IResourceTypeRepository,
)
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminInboxItem,
    AdminInboxPayload,
    AdminNotifyInput,
    CreateResourceTypeSchema,
    OutboxItem,
    ResourceTypeSchema,
    UpdateResourceTypeSchema,
)
from platform.features.communication.messaging.inbox.models import (
    AdminInboxNotification,
    AdminInboxRecipient,
    AdminNotificationOutbox,
    NotificationResourceType,
)


class DjangoOutboxRepository(IOutboxRepository):

    def create(self, data: AdminNotifyInput) -> OutboxItem:
        obj = AdminNotificationOutbox.objects.create(
            admin_id=data.admin_id,
            admin_label=data.admin_label,
            scope=data.audience.scope.value,
            target_company_id=data.audience.target_company_id,
            target_user_id=data.audience.target_user_id,
            title=data.title,
            body=data.body,
            level=data.level.value,
            status=OutboxStatus.PENDING.value,
        )
        return OutboxItem.model_validate(obj)

    def get(self, outbox_id: uuid.UUID) -> Optional[OutboxItem]:
        try:
            return OutboxItem.model_validate(AdminNotificationOutbox.objects.get(id=outbox_id))
        except AdminNotificationOutbox.DoesNotExist:
            return None

    def set_status(
        self,
        outbox_id: uuid.UUID,
        status: OutboxStatus,
        recipients_count: Optional[int] = None,
        error_detail: str = '',
    ) -> None:
        fields = {'status': status.value, 'error_detail': error_detail}
        if recipients_count is not None:
            fields['recipients_count'] = recipients_count
        if status in (OutboxStatus.SENT, OutboxStatus.FAILED):
            fields['dispatched_at'] = timezone.now()
        AdminNotificationOutbox.objects.filter(id=outbox_id).update(**fields)

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = AdminNotificationOutbox.objects.all().order_by('-created_at')
        f = query.filters
        if 'status' in f:
            qs = qs.filter(status=f['status'])
        if 'scope' in f:
            qs = qs.filter(scope=f['scope'])

        total = qs.count()
        rows = list(qs[query.offset: query.offset + query.limit])
        items = [OutboxItem.model_validate(r) for r in rows]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )


class DjangoResourceTypeRepository(IResourceTypeRepository):

    def list(self, only_active: bool = False) -> List[ResourceTypeSchema]:
        qs = NotificationResourceType.objects.all().order_by('label')
        if only_active:
            qs = qs.filter(is_active=True)
        return [ResourceTypeSchema.model_validate(r) for r in qs]

    def get_by_code(self, code: str) -> Optional[ResourceTypeSchema]:
        try:
            return ResourceTypeSchema.model_validate(
                NotificationResourceType.objects.get(code=code)
            )
        except NotificationResourceType.DoesNotExist:
            return None

    def create(self, data: CreateResourceTypeSchema) -> ResourceTypeSchema:
        obj = NotificationResourceType.objects.create(**data.model_dump())
        return ResourceTypeSchema.model_validate(obj)

    def update(self, code: str, data: UpdateResourceTypeSchema) -> Optional[ResourceTypeSchema]:
        try:
            obj = NotificationResourceType.objects.get(code=code)
        except NotificationResourceType.DoesNotExist:
            return None
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(obj, field, value)
        if changes:
            obj.save(update_fields=[*changes.keys(), 'updated_at'])
        return ResourceTypeSchema.model_validate(obj)


def _admin_inbox_item(recipient) -> AdminInboxItem:
    n = recipient.notification
    try:
        level = NotificationLevel(n.level)
    except ValueError:
        level = NotificationLevel.INFO
    return AdminInboxItem(
        id=recipient.id,
        notification_id=n.id,
        kind=n.kind,
        actor_kind=n.actor_kind,
        actor_label=n.actor_label,
        title=n.title,
        body=n.body,
        level=level,
        resource_type_code=n.resource_type_code,
        resource_id=n.resource_id,
        resource_route=n.resource_route,
        read_at=recipient.read_at,
        created_at=recipient.created_at,
    )


class DjangoAdminInboxRepository(IAdminInboxRepository):

    def create_notification(self, payload: AdminInboxPayload) -> uuid.UUID:
        obj = AdminInboxNotification.objects.create(
            kind=payload.kind,
            actor_kind=payload.actor_kind,
            actor_id=payload.actor_id,
            actor_label=payload.actor_label,
            title=payload.title,
            body=payload.body,
            level=payload.level.value,
            resource_type_code=payload.resource_type_code,
            resource_id=payload.resource_id,
            resource_route=payload.resource_route,
        )
        return obj.id

    def add_recipients(self, notification_id: uuid.UUID, user_ids: List[uuid.UUID]) -> int:
        rows = [
            AdminInboxRecipient(notification_id=notification_id, user_id=uid)
            for uid in dict.fromkeys(user_ids)
        ]
        created = AdminInboxRecipient.objects.bulk_create(rows, ignore_conflicts=True)
        return len(created)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        status: ReadStatus,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminInboxItem], int]:
        qs = (
            AdminInboxRecipient.objects
            .select_related('notification')
            .filter(user_id=user_id, archived_at__isnull=True)
        )
        if status == ReadStatus.UNREAD:
            qs = qs.filter(read_at__isnull=True)
        elif status == ReadStatus.READ:
            qs = qs.filter(read_at__isnull=False)
        qs = qs.order_by('-created_at')
        total = qs.count()
        rows = list(qs[offset: offset + limit])
        return [_admin_inbox_item(r) for r in rows], total

    def unread_count(self, user_id: uuid.UUID) -> int:
        return AdminInboxRecipient.objects.filter(
            user_id=user_id, read_at__isnull=True, archived_at__isnull=True,
        ).count()

    def mark_read(self, user_id: uuid.UUID, recipient_id: Optional[uuid.UUID]) -> int:
        qs = AdminInboxRecipient.objects.filter(
            user_id=user_id,
            read_at__isnull=True,
            archived_at__isnull=True,
        )
        if recipient_id is not None:
            qs = qs.filter(id=recipient_id)
        return qs.update(read_at=timezone.now())

    def archive(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
        return AdminInboxRecipient.objects.filter(
            user_id=user_id, id=recipient_id, archived_at__isnull=True,
        ).update(archived_at=timezone.now())


class DjangoAdminFeatureAudienceLookup(IAdminFeatureAudienceLookup):

    def user_ids_for_feature(self, feature_key: str) -> List[uuid.UUID]:
        from django.db.models import Q

        from platform.features.security.identity.users.models import AdminUser

        key = (feature_key or '').strip()
        if not key:
            return []
        qs = AdminUser.objects.filter(is_active=True).filter(
            Q(is_superuser=True)
            | Q(
                role__is_active=True,
                role__rol_features__feature__key=key,
                role__rol_features__feature__is_active=True,
            )
        )
        return list(qs.values_list('id', flat=True).distinct())
