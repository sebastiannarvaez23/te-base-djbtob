"""Use cases for live support sessions."""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException, ValidationAppException
from core.trace import trace_layer
from platform.features.support.sessions.session.domain import constants as c
from platform.features.support.sessions.session.domain.interfaces import (
    ISupportSessionNotifier,
    ISupportSessionRealtime,
    ISupportSessionRepository,
    ISupportSettingsRepository,
)
from platform.features.support.sessions.session.domain.schemas import (
    AcceptSupportSessionSchema,
    CreateSupportSessionSchema,
    RateSupportSessionSchema,
    SendSupportMessageSchema,
    SupportSessionEventView,
    SupportSessionListFilters,
    SupportSessionMessageView,
    SupportSessionView,
    SupportSettingsSchema,
    UpdateSupportSettingsSchema,
)

# Re-export for callers / tests that imported copy from this module.
ASK_MOTIVE_MESSAGE = c.ASK_MOTIVE_MESSAGE
AGENT_JOINED_MESSAGE = c.AGENT_JOINED_MESSAGE
RATING_REQUEST_MESSAGE = c.RATING_REQUEST_MESSAGE


class CreateSupportSessionUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        notifier: ISupportSessionNotifier,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._notifier = notifier
        self._realtime = realtime

    @trace_layer('application')
    def execute(self, data: CreateSupportSessionSchema) -> SupportSessionView:
        existing = self._repo.get_open_for_requester(data.requester_user_id)
        if existing is not None:
            raise ConflictException(AppErrorCode.SSES_ALREADY_OPEN)

        session = self._repo.create_session(
            data,
            ask_motive_message=c.ASK_MOTIVE_MESSAGE,
        )
        self._notifier.notify_queued(session)
        self._realtime.push_session(session, event_type='support.session.updated')
        return session


class GetActiveClientSessionUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, requester_user_id: UUID) -> SupportSessionView | None:
        return self._repo.get_open_for_requester(requester_user_id)


class GetActiveAgentSessionUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, admin_user_id: UUID) -> SupportSessionView | None:
        return self._repo.get_active_for_agent(admin_user_id)


class GetSupportSessionUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, session_id: UUID) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        return session


class ListSupportSessionsUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(
        self,
        filters: SupportSessionListFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionView], int]:
        return self._repo.list_sessions(filters, limit=limit, offset=offset)


class AcceptSupportSessionUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        notifier: ISupportSessionNotifier,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._notifier = notifier
        self._realtime = realtime

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        data: AcceptSupportSessionSchema,
    ) -> SupportSessionView:
        # Busy + status checks run inside repository.accept (same atomic lock).
        session = self._repo.accept(
            session_id,
            admin_user_id=data.admin_user_id,
            admin_label=data.admin_label,
            system_message=c.AGENT_JOINED_MESSAGE,
        )
        self._notifier.notify_accepted(session, exclude_admin_id=data.admin_user_id)
        self._realtime.push_session(session, event_type='support.accepted')
        return session


class SendClientMessageUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        *,
        requester_user_id: UUID,
        data: SendSupportMessageSchema,
    ) -> SupportSessionMessageView:
        session = self._require_client_session(session_id, requester_user_id)
        if session.status not in (c.STATUS_QUEUED, c.STATUS_ACTIVE):
            raise ConflictException(AppErrorCode.SSES_INVALID_STATUS)

        message = self._repo.add_message(
            session_id,
            sender_kind=c.SENDER_CLIENT,
            sender_user_id=requester_user_id,
            body=data.body,
            bump_agent_unread=True,
        )
        refreshed = self._repo.get(session_id)
        if refreshed is not None:
            self._realtime.push_message(refreshed, message)
            self._realtime.push_session(refreshed, event_type='support.unread')
        return message

    def _require_client_session(
        self,
        session_id: UUID,
        requester_user_id: UUID,
    ) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.requester_user_id != requester_user_id:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        return session


class SendAgentMessageUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        *,
        admin_user_id: UUID,
        data: SendSupportMessageSchema,
    ) -> SupportSessionMessageView:
        session = self._require_agent_session(session_id, admin_user_id)
        if session.status != c.STATUS_ACTIVE:
            raise ConflictException(AppErrorCode.SSES_INVALID_STATUS)

        message = self._repo.add_message(
            session_id,
            sender_kind=c.SENDER_AGENT,
            sender_user_id=admin_user_id,
            body=data.body,
            bump_client_unread=True,
        )
        refreshed = self._repo.get(session_id)
        if refreshed is not None:
            self._realtime.push_message(refreshed, message)
            self._realtime.push_session(refreshed, event_type='support.unread')
        return message

    def _require_agent_session(
        self,
        session_id: UUID,
        admin_user_id: UUID,
    ) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.accepted_by_id != admin_user_id:
            raise ConflictException(AppErrorCode.SSES_NOT_ASSIGNED)
        return session


class MarkClientReadUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(self, session_id: UUID, *, requester_user_id: UUID) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None or session.requester_user_id != requester_user_id:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        updated = self._repo.mark_read_client(session_id)
        self._realtime.push_session(updated, event_type='support.unread')
        return updated


class MarkAgentReadUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(self, session_id: UUID, *, admin_user_id: UUID) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.accepted_by_id != admin_user_id:
            raise ConflictException(AppErrorCode.SSES_NOT_ASSIGNED)
        updated = self._repo.mark_read_agent(session_id)
        self._realtime.push_session(updated, event_type='support.unread')
        return updated


class CancelSupportSessionUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(self, session_id: UUID, *, requester_user_id: UUID) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None or session.requester_user_id != requester_user_id:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.status != c.STATUS_QUEUED:
            raise ConflictException(AppErrorCode.SSES_INVALID_STATUS)
        updated = self._repo.cancel(session_id)
        self._realtime.push_session(updated, event_type='support.closed')
        return updated


class CloseSupportSessionUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(self, session_id: UUID, *, admin_user_id: UUID) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.accepted_by_id != admin_user_id:
            raise ConflictException(AppErrorCode.SSES_NOT_ASSIGNED)
        if session.status != c.STATUS_ACTIVE:
            raise ConflictException(AppErrorCode.SSES_INVALID_STATUS)
        updated = self._repo.close_for_rating(
            session_id,
            system_message=c.RATING_REQUEST_MESSAGE,
        )
        self._realtime.push_session(updated, event_type='support.rating_requested')
        return updated


class RateSupportSessionUseCase:
    def __init__(
        self,
        repository: ISupportSessionRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        *,
        requester_user_id: UUID,
        data: RateSupportSessionSchema,
    ) -> SupportSessionView:
        session = self._repo.get(session_id)
        if session is None or session.requester_user_id != requester_user_id:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if session.status != c.STATUS_AWAITING_RATING:
            raise ConflictException(AppErrorCode.SSES_INVALID_STATUS)
        if data.rating < 1 or data.rating > 5:
            raise ValidationAppException(AppErrorCode.SSES_INVALID_RATING)
        updated = self._repo.rate(
            session_id,
            rating=data.rating,
            comment=data.comment or '',
        )
        self._realtime.push_session(updated, event_type='support.closed')
        return updated


class ListSupportMessagesUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
        requester_user_id: UUID | None = None,
    ) -> tuple[list[SupportSessionMessageView], int]:
        session = self._repo.get(session_id)
        if session is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        if (
            requester_user_id is not None
            and session.requester_user_id != requester_user_id
        ):
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        return self._repo.list_messages(session_id, limit=limit, offset=offset)


class ListSupportEventsUseCase:
    def __init__(self, repository: ISupportSessionRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionEventView], int]:
        if self._repo.get(session_id) is None:
            raise NotFoundException(AppErrorCode.SSES_NOT_FOUND)
        return self._repo.list_events(session_id, limit=limit, offset=offset)


def _default_support_settings() -> SupportSettingsSchema:
    return SupportSettingsSchema()


class GetSupportSettingsUseCase:
    def __init__(self, repository: ISupportSettingsRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self) -> SupportSettingsSchema:
        return self._repo.get() or _default_support_settings()


class UpdateSupportSettingsUseCase:
    def __init__(self, repository: ISupportSettingsRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, data: UpdateSupportSettingsSchema) -> SupportSettingsSchema:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        current = self._repo.get() or _default_support_settings()
        try:
            updated = SupportSettingsSchema(**{**current.model_dump(), **fields})
        except ValidationError as exc:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR) from exc
        return self._repo.save(updated)


class ExpireStaleSupportSessionsUseCase:
    """Server-side queue timeout + awaiting-rating TTL sweeper."""

    def __init__(
        self,
        repository: ISupportSessionRepository,
        settings_repository: ISupportSettingsRepository,
        realtime: ISupportSessionRealtime,
    ):
        self._repo = repository
        self._settings = settings_repository
        self._realtime = realtime

    @trace_layer('application')
    def execute(self) -> dict[str, int]:
        settings = self._settings.get() or _default_support_settings()
        cancelled = self._repo.cancel_expired_queued(
            older_than_minutes=settings.queue_wait_timeout_minutes,
        )
        closed = self._repo.close_stale_awaiting_rating(
            older_than_hours=c.AWAITING_RATING_TTL_HOURS,
        )
        for session in cancelled:
            self._realtime.push_session(session, event_type='support.closed')
        for session in closed:
            self._realtime.push_session(session, event_type='support.closed')
        return {
            'cancelled_queued': len(cancelled),
            'closed_awaiting_rating': len(closed),
        }
