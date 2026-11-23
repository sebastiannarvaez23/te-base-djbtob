"""
OutboxIncidentReporterNotifier — avisa al reporter vía campanita (inbox).

Reutiliza el outbox admin → fan-out Celery → ``Notification`` en el schema
del tenant. Best-effort: un fallo de envío no revierte el cambio de estado.
"""

from __future__ import annotations

import logging
import uuid
from typing import Protocol

from platform.features.communication.messaging.inbox.domain.enums import (
    AudienceScope,
    NotificationLevel,
)
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminNotifyInput,
    Audience,
)
from platform.features.support.incidents.incident.domain.interfaces import IIncidentReporterNotifier
from platform.features.support.incidents.incident.domain.schemas import IncidentView

logger = logging.getLogger('app.api')

_STATUS_LABELS = {
    'open': 'Abierta',
    'in_progress': 'En progreso',
    'resolved': 'Resuelta',
    'closed': 'Cerrada',
    'discarded': 'Descartada',
}


class SupportsAdminNotify(Protocol):
    """Puerto estrecho: solo ``execute(AdminNotifyInput)`` del inbox platform."""

    def execute(self, data: AdminNotifyInput):
        ...


class OutboxIncidentReporterNotifier(IIncidentReporterNotifier):

    def __init__(self, notify_use_case: SupportsAdminNotify):
        self._notify = notify_use_case

    def notify_status_changed(
        self,
        incident: IncidentView,
        *,
        previous_status: str,
        admin_id: str,
        admin_label: str,
    ) -> None:
        if previous_status == incident.status:
            return

        reporter_id = self._parse_reporter_uuid(incident.reporter_user_id)
        if reporter_id is None:
            logger.info(
                'INCIDENT_STATUS_NOTIFY_SKIP code=%s reason=no_reporter',
                incident.code,
            )
            return

        try:
            admin_uuid = uuid.UUID(str(admin_id))
        except (TypeError, ValueError):
            logger.warning(
                'INCIDENT_STATUS_NOTIFY_SKIP code=%s reason=bad_admin_id',
                incident.code,
            )
            return

        prev_label = _STATUS_LABELS.get(previous_status, previous_status)
        next_label = _STATUS_LABELS.get(incident.status, incident.status)
        title = f'Incidencia {incident.code}: {next_label}'
        body = (
            f'Tu incidencia {incident.code} cambió de estado: '
            f'{prev_label} → {next_label}.'
        )
        notes = (incident.resolution_notes or '').strip()
        if notes:
            body = f'{body}\n\nNotas: {notes}'

        try:
            self._notify.execute(
                AdminNotifyInput(
                    admin_id=admin_uuid,
                    admin_label=(admin_label or 'Soporte').strip() or 'Soporte',
                    title=title[:200],
                    body=body,
                    level=self._level_for(incident.status),
                    audience=Audience(
                        scope=AudienceScope.SINGLE_USER,
                        target_user_id=reporter_id,
                    ),
                ),
            )
        except Exception as exc:
            logger.warning(
                'INCIDENT_STATUS_NOTIFY_FAILED code=%s error=%s',
                incident.code, exc,
            )

    @staticmethod
    def _parse_reporter_uuid(raw: str) -> uuid.UUID | None:
        value = (raw or '').strip()
        if not value or value.lower() in {'system', 'none', 'null'}:
            return None
        try:
            return uuid.UUID(value)
        except ValueError:
            return None

    @staticmethod
    def _level_for(status: str) -> NotificationLevel:
        if status in ('resolved', 'closed'):
            return NotificationLevel.SUCCESS
        if status == 'discarded':
            return NotificationLevel.WARNING
        return NotificationLevel.INFO
