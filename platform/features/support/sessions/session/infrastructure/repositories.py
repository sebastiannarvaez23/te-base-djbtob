"""Django ORM repository for live support sessions."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException
from platform.features.support.sessions.session.domain import constants as c
from platform.features.support.sessions.session.domain.interfaces import (
    ISupportSessionRepository,
    ISupportSettingsRepository,
)
from platform.features.support.sessions.session.domain.schemas import (
    CreateSupportSessionSchema,
    SupportSessionEventView,
    SupportSessionListFilters,
    SupportSessionMessageView,
    SupportSessionView,
    SupportSettingsSchema,
    normalize_whatsapp_url,
)
from platform.features.support.sessions.session.models import (
    SupportSession,
    SupportSessionEvent,
    SupportSessionMessage,
    SupportSettings,
)


def _session_view(obj: SupportSession) -> SupportSessionView:
    return SupportSessionView(
        id=obj.id,
        company_id=obj.company_id,
        schema_name=obj.schema_name,
        company_name=obj.company_name,
        requester_user_id=obj.requester_user_id,
        requester_username=obj.requester_username,
        requester_display_name=obj.requester_display_name,
        motive=obj.motive,
        status=obj.status,
        accepted_by_id=obj.accepted_by_id,
        accepted_by_label=obj.accepted_by_label or '',
        client_unread_count=obj.client_unread_count,
        agent_unread_count=obj.agent_unread_count,
        rating=obj.rating,
        rating_comment=obj.rating_comment or '',
        queued_at=obj.queued_at,
        accepted_at=obj.accepted_at,
        closed_at=obj.closed_at,
        rated_at=obj.rated_at,
        updated_at=obj.updated_at,
    )


def _message_view(obj: SupportSessionMessage) -> SupportSessionMessageView:
    return SupportSessionMessageView(
        id=obj.id,
        session_id=obj.session_id,
        sender_kind=obj.sender_kind,
        sender_user_id=obj.sender_user_id,
        body=obj.body,
        created_at=obj.created_at,
    )


def _event_view(obj: SupportSessionEvent) -> SupportSessionEventView:
    return SupportSessionEventView(
        id=obj.id,
        session_id=obj.session_id,
        event_type=obj.event_type,
        actor_kind=obj.actor_kind or '',
        actor_user_id=obj.actor_user_id,
        actor_label=obj.actor_label or '',
        payload=obj.payload or {},
        created_at=obj.created_at,
    )


def _require_session(session_id: UUID) -> SupportSession:
    obj = (
        SupportSession.objects.select_for_update()
        .filter(id=session_id)
        .first()
    )
    if obj is None:
        raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
    return obj


def _integrity_is(exc: IntegrityError, constraint_name: str) -> bool:
    return constraint_name.lower() in str(exc).lower()


class DjangoSupportSessionRepository(ISupportSessionRepository):

    @transaction.atomic
    def create_session(
        self,
        data: CreateSupportSessionSchema,
        *,
        ask_motive_message: str,
    ) -> SupportSessionView:
        try:
            obj = SupportSession.objects.create(
                company_id=data.company_id,
                schema_name=data.schema_name,
                company_name=data.company_name or '',
                requester_user_id=data.requester_user_id,
                requester_username=data.requester_username or '',
                requester_display_name=data.requester_display_name or '',
                motive=data.motive,
                status=c.STATUS_QUEUED,
            )
        except IntegrityError as exc:
            if _integrity_is(exc, c.UQ_OPEN_REQUESTER):
                raise ConflictException(AppErrorCode.SSES_ALREADY_OPEN) from exc
            raise

        # Persist from the opening prompt so refresh restores full history.
        SupportSessionMessage.objects.create(
            session=obj,
            sender_kind=c.SENDER_SYSTEM,
            sender_user_id=None,
            body=ask_motive_message,
        )
        SupportSessionMessage.objects.create(
            session=obj,
            sender_kind=c.SENDER_CLIENT,
            sender_user_id=data.requester_user_id,
            body=data.motive,
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_CREATED,
            actor_kind='CLIENT',
            actor_user_id=data.requester_user_id,
            actor_label=data.requester_display_name or data.requester_username,
            payload={'motive': data.motive[:200]},
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_QUEUED,
            actor_kind='SYSTEM',
            payload={},
        )
        return _session_view(obj)

    def get(self, session_id: UUID) -> Optional[SupportSessionView]:
        obj = SupportSession.objects.filter(id=session_id).first()
        return _session_view(obj) if obj else None

    def get_open_for_requester(self, requester_user_id: UUID) -> Optional[SupportSessionView]:
        obj = (
            SupportSession.objects.filter(
                requester_user_id=requester_user_id,
                status__in=c.OPEN_STATUSES,
            )
            .order_by('-queued_at')
            .first()
        )
        return _session_view(obj) if obj else None

    def get_active_for_agent(self, admin_user_id: UUID) -> Optional[SupportSessionView]:
        obj = (
            SupportSession.objects.filter(
                accepted_by_id=admin_user_id,
                status=c.STATUS_ACTIVE,
            )
            .order_by('-accepted_at')
            .first()
        )
        return _session_view(obj) if obj else None

    def list_sessions(
        self,
        filters: SupportSessionListFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionView], int]:
        qs = SupportSession.objects.all()
        if filters.status:
            qs = qs.filter(status=filters.status)
        if filters.company:
            term = filters.company.strip()
            qs = qs.filter(
                Q(company_name__icontains=term) | Q(schema_name__icontains=term)
            )
        if filters.from_date:
            qs = qs.filter(queued_at__gte=filters.from_date)
        if filters.to_date:
            qs = qs.filter(queued_at__lte=filters.to_date)
        if filters.search:
            term = filters.search.strip()
            qs = qs.filter(
                Q(motive__icontains=term)
                | Q(requester_username__icontains=term)
                | Q(requester_display_name__icontains=term)
                | Q(company_name__icontains=term)
            )
        total = qs.count()
        rows = list(qs.order_by('-queued_at')[offset:offset + limit])
        return [_session_view(r) for r in rows], total

    @transaction.atomic
    def accept(
        self,
        session_id: UUID,
        *,
        admin_user_id: UUID,
        admin_label: str,
        system_message: str,
    ) -> SupportSessionView:
        obj = _require_session(session_id)

        # Same atomic: lock any ACTIVE row for this agent before claiming.
        busy = (
            SupportSession.objects.select_for_update()
            .filter(
                accepted_by_id=admin_user_id,
                status=c.STATUS_ACTIVE,
            )
            .exclude(id=session_id)
            .first()
        )
        if busy is not None:
            raise ConflictException(AppErrorCode.SSES_AGENT_BUSY)

        if obj.status != c.STATUS_QUEUED:
            SupportSessionEvent.objects.create(
                session=obj,
                event_type=SupportSessionEvent.EVENT_ACCEPT_CONFLICT,
                actor_kind='AGENT',
                actor_user_id=admin_user_id,
                actor_label=admin_label or '',
            )
            raise ConflictException(AppErrorCode.SSES_ALREADY_ACCEPTED)

        obj.status = c.STATUS_ACTIVE
        obj.accepted_by_id = admin_user_id
        obj.accepted_by_label = admin_label or ''
        obj.accepted_at = timezone.now()
        try:
            obj.save(
                update_fields=[
                    'status',
                    'accepted_by_id',
                    'accepted_by_label',
                    'accepted_at',
                    'updated_at',
                ]
            )
        except IntegrityError as exc:
            if _integrity_is(exc, c.UQ_ACTIVE_AGENT):
                raise ConflictException(AppErrorCode.SSES_AGENT_BUSY) from exc
            raise

        SupportSessionMessage.objects.create(
            session=obj,
            sender_kind=c.SENDER_SYSTEM,
            body=system_message,
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_ACCEPTED,
            actor_kind='AGENT',
            actor_user_id=admin_user_id,
            actor_label=admin_label or '',
        )
        return _session_view(obj)

    @transaction.atomic
    def add_message(
        self,
        session_id: UUID,
        *,
        sender_kind: str,
        sender_user_id: Optional[UUID],
        body: str,
        bump_client_unread: bool = False,
        bump_agent_unread: bool = False,
    ) -> SupportSessionMessageView:
        obj = _require_session(session_id)
        msg = SupportSessionMessage.objects.create(
            session=obj,
            sender_kind=sender_kind,
            sender_user_id=sender_user_id,
            body=body,
        )
        updates = ['updated_at']
        if bump_client_unread:
            obj.client_unread_count = (obj.client_unread_count or 0) + 1
            updates.append('client_unread_count')
        if bump_agent_unread:
            obj.agent_unread_count = (obj.agent_unread_count or 0) + 1
            updates.append('agent_unread_count')
        obj.save(update_fields=updates)
        # Chat lines live in messages; lifecycle events stay in the event log.
        return _message_view(msg)

    def list_messages(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionMessageView], int]:
        qs = SupportSessionMessage.objects.filter(session_id=session_id)
        total = qs.count()
        rows = list(qs.order_by('created_at')[offset:offset + limit])
        return [_message_view(r) for r in rows], total

    def list_events(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionEventView], int]:
        qs = SupportSessionEvent.objects.filter(session_id=session_id)
        total = qs.count()
        rows = list(qs.order_by('created_at')[offset:offset + limit])
        return [_event_view(r) for r in rows], total

    def add_event(
        self,
        session_id: UUID,
        *,
        event_type: str,
        actor_kind: str = '',
        actor_user_id: Optional[UUID] = None,
        actor_label: str = '',
        payload: Optional[dict] = None,
    ) -> SupportSessionEventView:
        evt = SupportSessionEvent.objects.create(
            session_id=session_id,
            event_type=event_type,
            actor_kind=actor_kind or '',
            actor_user_id=actor_user_id,
            actor_label=actor_label or '',
            payload=payload or {},
        )
        return _event_view(evt)

    @transaction.atomic
    def mark_read_client(self, session_id: UUID) -> SupportSessionView:
        obj = _require_session(session_id)
        obj.client_unread_count = 0
        obj.save(update_fields=['client_unread_count', 'updated_at'])
        return _session_view(obj)

    @transaction.atomic
    def mark_read_agent(self, session_id: UUID) -> SupportSessionView:
        obj = _require_session(session_id)
        obj.agent_unread_count = 0
        obj.save(update_fields=['agent_unread_count', 'updated_at'])
        return _session_view(obj)

    @transaction.atomic
    def cancel(self, session_id: UUID) -> SupportSessionView:
        obj = _require_session(session_id)
        obj.status = c.STATUS_CANCELLED
        obj.closed_at = timezone.now()
        obj.client_unread_count = 0
        obj.agent_unread_count = 0
        obj.save(
            update_fields=[
                'status',
                'closed_at',
                'client_unread_count',
                'agent_unread_count',
                'updated_at',
            ]
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_CANCELLED,
            actor_kind='CLIENT',
            actor_user_id=obj.requester_user_id,
        )
        return _session_view(obj)

    @transaction.atomic
    def close_for_rating(
        self,
        session_id: UUID,
        *,
        system_message: str,
    ) -> SupportSessionView:
        obj = _require_session(session_id)
        obj.status = c.STATUS_AWAITING_RATING
        obj.closed_at = timezone.now()
        obj.save(update_fields=['status', 'closed_at', 'updated_at'])
        SupportSessionMessage.objects.create(
            session=obj,
            sender_kind=c.SENDER_SYSTEM,
            body=system_message,
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_CLOSED,
            actor_kind='AGENT',
            actor_user_id=obj.accepted_by_id,
            actor_label=obj.accepted_by_label or '',
        )
        return _session_view(obj)

    @transaction.atomic
    def rate(
        self,
        session_id: UUID,
        *,
        rating: int,
        comment: str,
    ) -> SupportSessionView:
        obj = _require_session(session_id)
        obj.status = c.STATUS_CLOSED
        obj.rating = rating
        obj.rating_comment = comment or ''
        obj.rated_at = timezone.now()
        obj.client_unread_count = 0
        obj.agent_unread_count = 0
        obj.save(
            update_fields=[
                'status',
                'rating',
                'rating_comment',
                'rated_at',
                'client_unread_count',
                'agent_unread_count',
                'updated_at',
            ]
        )
        SupportSessionEvent.objects.create(
            session=obj,
            event_type=SupportSessionEvent.EVENT_RATED,
            actor_kind='CLIENT',
            actor_user_id=obj.requester_user_id,
            payload={'rating': rating},
        )
        return _session_view(obj)

    @transaction.atomic
    def cancel_expired_queued(
        self,
        *,
        older_than_minutes: int,
    ) -> list[SupportSessionView]:
        cutoff = timezone.now() - timedelta(minutes=max(1, older_than_minutes))
        rows = list(
            SupportSession.objects.select_for_update()
            .filter(status=c.STATUS_QUEUED, queued_at__lt=cutoff)
            .order_by('queued_at')[:200]
        )
        closed: list[SupportSessionView] = []
        now = timezone.now()
        for obj in rows:
            obj.status = c.STATUS_CANCELLED
            obj.closed_at = now
            obj.client_unread_count = 0
            obj.agent_unread_count = 0
            obj.save(
                update_fields=[
                    'status',
                    'closed_at',
                    'client_unread_count',
                    'agent_unread_count',
                    'updated_at',
                ]
            )
            SupportSessionEvent.objects.create(
                session=obj,
                event_type=SupportSessionEvent.EVENT_CANCELLED,
                actor_kind='SYSTEM',
                payload={'reason': 'queue_timeout'},
            )
            closed.append(_session_view(obj))
        return closed

    @transaction.atomic
    def close_stale_awaiting_rating(
        self,
        *,
        older_than_hours: int,
    ) -> list[SupportSessionView]:
        cutoff = timezone.now() - timedelta(hours=max(1, older_than_hours))
        rows = list(
            SupportSession.objects.select_for_update()
            .filter(status=c.STATUS_AWAITING_RATING, closed_at__lt=cutoff)
            .order_by('closed_at')[:200]
        )
        closed: list[SupportSessionView] = []
        for obj in rows:
            obj.status = c.STATUS_CLOSED
            obj.save(update_fields=['status', 'updated_at'])
            SupportSessionEvent.objects.create(
                session=obj,
                event_type=SupportSessionEvent.EVENT_CLOSED,
                actor_kind='SYSTEM',
                payload={'reason': 'rating_timeout'},
            )
            closed.append(_session_view(obj))
        return closed


def _settings_schema(obj: SupportSettings) -> SupportSettingsSchema:
    raw_url = obj.whatsapp_url or ''
    try:
        whatsapp_url = normalize_whatsapp_url(raw_url)
    except ValueError:
        whatsapp_url = ''
    return SupportSettingsSchema(
        queue_wait_timeout_minutes=obj.queue_wait_timeout_minutes,
        whatsapp_url=whatsapp_url,
        phone_line=obj.phone_line or '',
    )


class DjangoSupportSettingsRepository(ISupportSettingsRepository):

    def get(self) -> Optional[SupportSettingsSchema]:
        obj = SupportSettings.objects.filter(
            singleton_key=SupportSettings.SINGLETON_KEY,
        ).first()
        if obj is None:
            return None
        return _settings_schema(obj)

    def save(self, data: SupportSettingsSchema) -> SupportSettingsSchema:
        try:
            whatsapp_url = normalize_whatsapp_url(data.whatsapp_url)
        except ValueError as exc:
            from core.errors.exceptions import ValidationAppException
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR) from exc
        obj, _ = SupportSettings.objects.update_or_create(
            singleton_key=SupportSettings.SINGLETON_KEY,
            defaults={
                'queue_wait_timeout_minutes': data.queue_wait_timeout_minutes,
                'whatsapp_url': whatsapp_url,
                'phone_line': (data.phone_line or '').strip(),
            },
        )
        return _settings_schema(obj)
