"""
PurgeIncidentsUseCase — retención de incidencias.

Elimina incidencias en estado terminal (resueltas/cerradas/descartadas) que no
se han tocado en ``days`` días. Las abiertas y en progreso nunca se purgan.
La evidencia adjunta en object storage se elimina tras borrar las filas.
"""

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentAttachmentRepository,
    IIncidentAttachmentStorage,
    IIncidentRepository,
)
from core.trace import trace_layer

logger = logging.getLogger('app.tasks')


class PurgeIncidentsUseCase:

    TERMINAL_STATUSES = {'resolved', 'closed', 'discarded'}

    def __init__(
        self,
        repository: IIncidentRepository,
        *,
        attachments: Optional[IIncidentAttachmentRepository] = None,
        storage: Optional[IIncidentAttachmentStorage] = None,
    ):
        self._repo = repository
        self._attachments = attachments
        self._storage = storage

    @trace_layer('application')
    def execute(self, days: int, statuses=None) -> int:
        cutoff = timezone.now() - timedelta(days=days)
        statuses = statuses or self.TERMINAL_STATUSES
        objects: list[str] = []
        if self._attachments is not None and self._storage is not None:
            objects = self._attachments.attachment_objects_for_purge(cutoff, statuses)
        deleted = self._repo.purge(cutoff, statuses)
        for object_name in objects:
            try:
                self._storage.delete(object_name)
            except Exception as exc:
                logger.warning(
                    'INCIDENT_ATTACHMENT_PURGE_FAILED object=%s error=%s', object_name, exc,
                )
        return deleted
