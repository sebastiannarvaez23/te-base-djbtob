"""Notify the admin inbox when an automated task fails.

Copy is English (API / catalog language); UI i18n can localize later.
"""

from __future__ import annotations

import logging
from uuid import UUID

from core.realtime.publisher import RealtimePublisherFactory
from platform.features.communication.messaging.inbox.application.use_cases import (
    DeliverAdminInboxUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel
from platform.features.communication.messaging.inbox.domain.schemas import AdminInboxPayload
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoAdminFeatureAudienceLookup,
    DjangoAdminInboxRepository,
)
from platform.features.support.ops.task_monitor.domain.catalog import get_task_def

logger = logging.getLogger('app.tasks')

AUTOMATED_TASK_ADMIN_FEATURE_KEY = 'support.automate-task'
_RESOURCE_TYPE = 'automated_task'
_RESOURCE_ROUTE = '/admin/support'


class AdminInboxTaskFailureNotifier:
    """Notifies AdminUsers whose role has ``support.automate-task``."""

    def __init__(self, lookup=None, deliver=None):
        self._lookup = lookup or DjangoAdminFeatureAudienceLookup()
        self._deliver = deliver or DeliverAdminInboxUseCase(
            DjangoAdminInboxRepository(),
            RealtimePublisherFactory.create(),
        )

    def notify_failed(
        self,
        *,
        task_key: str,
        run_id: UUID,
        error_summary: str = '',
    ) -> int:
        user_ids = self._lookup.user_ids_for_feature(AUTOMATED_TASK_ADMIN_FEATURE_KEY)
        if not user_ids:
            logger.info(
                'automated_task_failure_notify_skip task=%s reason=no_recipients',
                task_key,
            )
            return 0

        catalog = get_task_def(task_key)
        label = (catalog.title if catalog else '') or task_key
        error = (error_summary or '').strip() or 'The task ended with an error.'
        payload = AdminInboxPayload(
            title=f'Automated task failed: «{label}»'[:200],
            body=(
                f'{error}\n\nOpen it under Support → Automated tasks.'
            ),
            level=NotificationLevel.WARNING,
            kind='SYSTEM',
            actor_kind='SYSTEM',
            actor_label='Automated tasks',
            resource_type_code=_RESOURCE_TYPE,
            resource_id=run_id,
            resource_route=_RESOURCE_ROUTE,
        )
        return self._deliver.execute(payload, user_ids)
