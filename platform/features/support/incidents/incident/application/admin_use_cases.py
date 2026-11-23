"""
Casos de uso administrativos: listar, ver y gestionar el estado de incidencias.
"""

import logging
from typing import Optional

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException, ConflictException, ValidationAppException
from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentReporterNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentView
from core.trace import trace_layer

logger = logging.getLogger('app.api')

_VALID_STATUSES = {'open', 'in_progress', 'resolved', 'closed', 'discarded'}
_NEEDS_ASSIGNEE = {'in_progress', 'resolved', 'closed'}
_NEEDS_NOTES = {'resolved', 'closed'}


class IncidentNotFound(AppException):
    def __init__(self):
        super().__init__(AppErrorCode.INCIDENT_NOT_FOUND)


class ListIncidentsUseCase:
    def __init__(self, repository: IIncidentRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, filters: dict, limit: int = 50, offset: int = 0) -> list[IncidentView]:
        return self._repo.list(filters or {}, limit=limit, offset=offset)


class GetIncidentUseCase:
    def __init__(self, repository: IIncidentRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, incident_id: str) -> IncidentView:
        incident = self._repo.get(incident_id)
        if incident is None:
            raise IncidentNotFound()
        return incident


class UpdateIncidentStatusUseCase:
    def __init__(
        self,
        repository: IIncidentRepository,
        reporter_notifier: Optional[IIncidentReporterNotifier] = None,
    ):
        self._repo = repository
        self._reporter_notifier = reporter_notifier

    @trace_layer('application')
    def execute(
        self,
        incident_id: str,
        *,
        status: str,
        assigned_admin_id: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        admin_id: str = '',
        admin_label: str = '',
    ) -> IncidentView:
        if status not in _VALID_STATUSES:
            raise AppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f'Invalid status: {status!r}.',
            )

        previous = self._repo.get(incident_id)
        if previous is None:
            raise IncidentNotFound()

        assignee = assigned_admin_id or previous.assigned_admin_id or None
        if status in _NEEDS_ASSIGNEE and not assignee:
            raise ConflictException(AppErrorCode.INCIDENT_ASSIGNEE_REQUIRED)

        notes = (resolution_notes or '').strip()
        if status in _NEEDS_NOTES and not notes:
            raise ValidationAppException(AppErrorCode.INCIDENT_NOTES_REQUIRED)

        incident = self._repo.update_status(
            incident_id,
            status=status,
            assigned_admin_id=assigned_admin_id,
            resolution_notes=notes or None,
        )
        if incident is None:
            raise IncidentNotFound()

        if (
            self._reporter_notifier is not None
            and previous.status != incident.status
        ):
            try:
                self._reporter_notifier.notify_status_changed(
                    incident,
                    previous_status=previous.status,
                    admin_id=admin_id or incident.assigned_admin_id or '',
                    admin_label=admin_label or 'Soporte',
                )
            except Exception as exc:
                # El adaptador ya degrada; esto es red de seguridad.
                logger.warning(
                    'INCIDENT_STATUS_NOTIFY_SAFETY_NET code=%s error=%s',
                    incident.code, exc,
                )

        return incident
