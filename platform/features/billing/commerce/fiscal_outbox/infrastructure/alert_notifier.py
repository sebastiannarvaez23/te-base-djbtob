"""Admin bell (campanita) alerts for the base → Neurana fiscal sync.

Copy is English (API / catalog language) like the other admin inbox
notifiers; UI i18n can localize later. Every method is best-effort.
"""
from __future__ import annotations

import logging
from uuid import UUID

from django.core.cache import cache

from core.realtime.publisher import RealtimePublisherFactory
from platform.features.billing.commerce.fiscal_outbox.domain.interfaces import (
    IFiscalSyncAlertNotifier,
)
from platform.features.billing.commerce.fiscal_outbox.domain.schemas import (
    FiscalDeadReason,
    FiscalOutboxEventSchema,
    FiscalOutboxKind,
)
from platform.features.communication.messaging.inbox.application.use_cases import (
    DeliverAdminInboxUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel
from platform.features.communication.messaging.inbox.domain.schemas import AdminInboxPayload
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoAdminInboxRepository,
)

logger = logging.getLogger('billing.fiscal_outbox')

RESOURCE_TYPE = 'fiscal_invoice'
RESOURCE_ROUTE = '/admin/billing'
ACTOR_LABEL = 'Fiscal sync'
DEDUPE_SECONDS = 3600
DIGEST_THRESHOLD = 3

KEY_BREAKER_OPEN = 'fiscal_alert:breaker_open'
KEY_BACKLOG = 'fiscal_alert:backlog'


def _active_admin_ids() -> list[UUID]:
    from platform.features.security.identity.users.models import AdminUser

    return list(AdminUser.objects.filter(is_active=True).values_list('id', flat=True))


class FiscalSyncAlertNotifier(IFiscalSyncAlertNotifier):
    def __init__(self, deliver=None, recipients=None, store=None):
        self._deliver = deliver
        self._recipients = recipients or _active_admin_ids
        self._store = store or cache

    def _send(self, payload: AdminInboxPayload) -> int:
        user_ids = self._recipients()
        if not user_ids:
            logger.info('fiscal_alert_skip reason=no_recipients title=%s', payload.title)
            return 0
        deliver = self._deliver or DeliverAdminInboxUseCase(
            DjangoAdminInboxRepository(),
            RealtimePublisherFactory.create(),
        )
        return deliver.execute(payload, user_ids)

    def _payload(self, title: str, body: str, level: NotificationLevel, resource_id=None):
        return AdminInboxPayload(
            title=title[:200],
            body=body,
            level=level,
            kind='SYSTEM',
            actor_kind='SYSTEM',
            actor_label=ACTOR_LABEL,
            resource_type_code=RESOURCE_TYPE,
            resource_id=resource_id,
            resource_route=RESOURCE_ROUTE,
        )

    def breaker_changed(self, *, previous: str, new: str) -> None:
        if new == 'open':
            if not self._store.add(KEY_BREAKER_OPEN, 1, timeout=DEDUPE_SECONDS):
                return
            self._send(self._payload(
                'Neurana is unreachable: electronic invoicing paused',
                'The base keeps charging normally. Invoices are queued and will be sent '
                'to Neurana automatically as soon as it responds again.',
                NotificationLevel.WARNING,
            ))
        elif new == 'closed' and previous != 'closed':
            # Only announce recovery if the outage was announced.
            if not self._store.get(KEY_BREAKER_OPEN):
                return
            self._store.delete(KEY_BREAKER_OPEN)
            self._send(self._payload(
                'Neurana is back: electronic invoicing resumed',
                'Queued invoices are being sent now. No action needed.',
                NotificationLevel.SUCCESS,
            ))

    def backlog_stale(self, *, count: int, oldest_minutes: int) -> None:
        if count <= 0 or not self._store.add(KEY_BACKLOG, 1, timeout=DEDUPE_SECONDS):
            return
        noun = 'invoice is' if count == 1 else 'invoices are'
        self._send(self._payload(
            f'{count} {noun} waiting for electronic invoicing',
            f'The oldest has been waiting {oldest_minutes} minutes. The base retries '
            'automatically; if it keeps growing, check the Neurana connection.',
            NotificationLevel.WARNING,
        ))

    def dead_letters(self, events: list[FiscalOutboxEventSchema]) -> None:
        if not events:
            return
        if len(events) > DIGEST_THRESHOLD:
            rejected = sum(1 for e in events if e.dead_reason == FiscalDeadReason.REJECTED)
            self._send(self._payload(
                f'{len(events)} invoices could not be sent to Neurana',
                f'{rejected} were rejected by Neurana and {len(events) - rejected} ran out '
                'of retries. Review them in Billing and resend once corrected.',
                NotificationLevel.WARNING,
            ))
            return
        for event in events:
            self._send(self._payload(*self._dead_copy(event), NotificationLevel.WARNING,
                                     resource_id=event.invoice_id))

    @staticmethod
    def _dead_copy(event: FiscalOutboxEventSchema) -> tuple[str, str]:
        action = 'void' if event.kind == FiscalOutboxKind.VOID else 'electronic invoice'
        if event.dead_reason == FiscalDeadReason.REJECTED:
            return (
                f'Neurana rejected the {action}',
                'Check the customer tax data (NIT, legal name) on the invoice and resend it.',
            )
        return (
            f'The {action} could not be sent to Neurana',
            'Retries ran out after several days. Check the Neurana connection and resend it.',
        )
