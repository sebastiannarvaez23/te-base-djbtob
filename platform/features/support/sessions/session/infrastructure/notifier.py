"""Admin inbox fan-out for live support sessions."""

from __future__ import annotations

import logging
from uuid import UUID

from django.core.cache import cache

from core.realtime.publisher import RealtimePublisherFactory
from platform.features.communication.messaging.inbox.application.use_cases import (
    DeliverAdminInboxUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel
from platform.features.communication.messaging.inbox.domain.schemas import AdminInboxPayload
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoAdminInboxRepository,
)
from platform.features.support.sessions.session.domain import constants as c
from platform.features.support.sessions.session.domain.interfaces import (
    ISupportSessionNotifier,
)
from platform.features.support.sessions.session.domain.schemas import SupportSessionView

logger = logging.getLogger('app.api')

_RESOURCE_TYPE = 'support_session'
_RESOURCE_ROUTE = '/admin/support'
_KIND = 'SUPPORT_LIVE'


def _all_active_admin_ids() -> list[UUID]:
    """Active platform admins; short Redis cache avoids full-table scans on every queue event."""
    cached = cache.get(c.ADMIN_IDS_CACHE_KEY)
    if cached is not None:
        return [UUID(str(x)) for x in cached]

    from platform.features.security.identity.users.models import AdminUser

    ids = list(
        AdminUser.objects.filter(is_active=True).values_list('id', flat=True)
    )
    cache.set(
        c.ADMIN_IDS_CACHE_KEY,
        [str(i) for i in ids],
        timeout=c.ADMIN_IDS_CACHE_TTL_SECONDS,
    )
    return ids


class AdminInboxSupportSessionNotifier(ISupportSessionNotifier):
    """Delivers support-session alerts to every active AdminUser."""

    def __init__(self, deliver=None):
        self._deliver = deliver or DeliverAdminInboxUseCase(
            DjangoAdminInboxRepository(),
            RealtimePublisherFactory.create(),
        )

    def notify_queued(self, session: SupportSessionView) -> None:
        user_ids = _all_active_admin_ids()
        if not user_ids:
            logger.info('support_session_notify_skip reason=no_recipients')
            return

        requester = (
            session.requester_display_name
            or session.requester_username
            or 'User'
        )
        company = session.company_name or session.schema_name or 'Company'
        motive = (session.motive or '').strip()
        if len(motive) > 280:
            motive = motive[:277] + '...'

        payload = AdminInboxPayload(
            title=f'Support request · {company}'[:200],
            body=(
                f'{requester} (@{session.requester_username or "—"})\n'
                f'Company: {company}\n'
                f'Reason: {motive}'
            ),
            level=NotificationLevel.WARNING,
            kind=_KIND,
            actor_kind='CLIENT',
            actor_label=requester[:120],
            actor_id=session.requester_user_id,
            resource_type_code=_RESOURCE_TYPE,
            resource_id=session.id,
            resource_route=_RESOURCE_ROUTE,
        )
        self._deliver.execute(payload, user_ids)

    def notify_accepted(
        self,
        session: SupportSessionView,
        *,
        exclude_admin_id: UUID,
    ) -> None:
        user_ids = [
            uid for uid in _all_active_admin_ids() if uid != exclude_admin_id
        ]
        if not user_ids:
            return

        agent = session.accepted_by_label or 'An agent'
        company = session.company_name or session.schema_name or 'Company'
        payload = AdminInboxPayload(
            title=f'Support case taken · {company}'[:200],
            body=(
                f'{agent} accepted the support request from '
                f'{session.requester_display_name or session.requester_username}.'
            ),
            level=NotificationLevel.INFO,
            kind=_KIND,
            actor_kind='AGENT',
            actor_label=agent[:120],
            actor_id=session.accepted_by_id,
            resource_type_code=_RESOURCE_TYPE,
            resource_id=session.id,
            resource_route=_RESOURCE_ROUTE,
        )
        self._deliver.execute(payload, user_ids)
