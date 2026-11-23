"""Realtime pushes for live support sessions via core publisher."""

from __future__ import annotations

import logging
from typing import Optional

from core.realtime.envelope import RealtimeMessage
from core.realtime.groups import RealtimeGroups
from core.realtime.publisher import IRealtimePublisher, RealtimePublisherFactory
from platform.features.support.sessions.session.domain import constants as c
from platform.features.support.sessions.session.domain.interfaces import (
    ISupportSessionRealtime,
)
from platform.features.support.sessions.session.domain.schemas import (
    SupportSessionMessageView,
    SupportSessionView,
)

logger = logging.getLogger('app.api')

# Board-level events every connected admin agent should see (queue / accept / close).
_BOARD_EVENT_TYPES = frozenset({
    'support.session.updated',
    'support.accepted',
    'support.closed',
    'support.rating_requested',
})


class ChannelsSupportSessionRealtime(ISupportSessionRealtime):

    def __init__(self, publisher: IRealtimePublisher | None = None):
        self._publisher = publisher or RealtimePublisherFactory.create()

    def push_session(
        self,
        session: SupportSessionView,
        *,
        event_type: str,
        extra: Optional[dict] = None,
    ) -> None:
        payload = {
            'session': session.model_dump(mode='json'),
            **(extra or {}),
        }
        message = RealtimeMessage(type=event_type, payload=payload)
        self._to_client(session, message)
        self._to_agent(session, message)
        if event_type in _BOARD_EVENT_TYPES or session.status == c.STATUS_QUEUED:
            self._to_admin_board(message)

    def push_message(
        self,
        session: SupportSessionView,
        message: SupportSessionMessageView,
    ) -> None:
        wire = RealtimeMessage(
            type='support.message',
            payload={
                'session_id': str(session.id),
                'message': message.model_dump(mode='json'),
                'client_unread_count': session.client_unread_count,
                'agent_unread_count': session.agent_unread_count,
            },
        )
        self._to_client(session, wire)
        self._to_agent(session, wire)

    def _to_client(self, session: SupportSessionView, message: RealtimeMessage) -> None:
        try:
            self._publisher.to_user(
                session.schema_name,
                session.requester_user_id,
                message,
            )
        except Exception:
            logger.exception(
                'support_session_realtime_client_failed session_id=%s',
                session.id,
            )

    def _to_agent(self, session: SupportSessionView, message: RealtimeMessage) -> None:
        if session.accepted_by_id is None:
            return
        try:
            self._publisher.to_user('public', session.accepted_by_id, message)
        except Exception:
            logger.exception(
                'support_session_realtime_agent_failed session_id=%s',
                session.id,
            )

    def _to_admin_board(self, message: RealtimeMessage) -> None:
        try:
            self._publisher.to_group(RealtimeGroups.platform_support(), message)
        except Exception:
            logger.exception('support_session_realtime_board_failed')
