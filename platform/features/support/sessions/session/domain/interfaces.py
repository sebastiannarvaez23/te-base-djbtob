"""Ports for live support sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from platform.features.support.sessions.session.domain.schemas import (
    CreateSupportSessionSchema,
    SupportSessionEventView,
    SupportSessionListFilters,
    SupportSessionMessageView,
    SupportSessionView,
    SupportSettingsSchema,
)


class ISupportSessionRepository(ABC):

    @abstractmethod
    def create_session(
        self,
        data: CreateSupportSessionSchema,
        *,
        ask_motive_message: str,
    ) -> SupportSessionView:
        ...

    @abstractmethod
    def get(self, session_id: UUID) -> Optional[SupportSessionView]:
        ...

    @abstractmethod
    def get_open_for_requester(self, requester_user_id: UUID) -> Optional[SupportSessionView]:
        ...

    @abstractmethod
    def get_active_for_agent(self, admin_user_id: UUID) -> Optional[SupportSessionView]:
        ...

    @abstractmethod
    def list_sessions(
        self,
        filters: SupportSessionListFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionView], int]:
        ...

    @abstractmethod
    def accept(
        self,
        session_id: UUID,
        *,
        admin_user_id: UUID,
        admin_label: str,
        system_message: str,
    ) -> SupportSessionView:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def list_messages(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionMessageView], int]:
        ...

    @abstractmethod
    def list_events(
        self,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupportSessionEventView], int]:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def mark_read_client(self, session_id: UUID) -> SupportSessionView:
        ...

    @abstractmethod
    def mark_read_agent(self, session_id: UUID) -> SupportSessionView:
        ...

    @abstractmethod
    def cancel(self, session_id: UUID) -> SupportSessionView:
        ...

    @abstractmethod
    def close_for_rating(
        self,
        session_id: UUID,
        *,
        system_message: str,
    ) -> SupportSessionView:
        ...

    @abstractmethod
    def rate(
        self,
        session_id: UUID,
        *,
        rating: int,
        comment: str,
    ) -> SupportSessionView:
        ...

    @abstractmethod
    def cancel_expired_queued(
        self,
        *,
        older_than_minutes: int,
    ) -> list[SupportSessionView]:
        """Cancel QUEUED sessions older than the wait timeout. Returns cancelled views."""
        ...

    @abstractmethod
    def close_stale_awaiting_rating(
        self,
        *,
        older_than_hours: int,
    ) -> list[SupportSessionView]:
        """Close AWAITING_RATING past TTL without a rating. Returns closed views."""
        ...


class ISupportSessionNotifier(ABC):

    @abstractmethod
    def notify_queued(self, session: SupportSessionView) -> None:
        ...

    @abstractmethod
    def notify_accepted(self, session: SupportSessionView, *, exclude_admin_id: UUID) -> None:
        ...


class ISupportSessionRealtime(ABC):

    @abstractmethod
    def push_session(
        self,
        session: SupportSessionView,
        *,
        event_type: str,
        extra: Optional[dict] = None,
    ) -> None:
        ...

    @abstractmethod
    def push_message(
        self,
        session: SupportSessionView,
        message: SupportSessionMessageView,
    ) -> None:
        ...


class ISupportSettingsRepository(ABC):

    @abstractmethod
    def get(self) -> Optional[SupportSettingsSchema]:
        ...

    @abstractmethod
    def save(self, data: SupportSettingsSchema) -> SupportSettingsSchema:
        ...
