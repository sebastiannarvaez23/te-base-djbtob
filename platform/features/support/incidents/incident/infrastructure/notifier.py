"""
CeleryIncidentNotifier — notifica al admin de forma asíncrona (best-effort).

Encola la tarea ``incident.notify_created`` para no añadir latencia al reporte.
Si el broker no está disponible, se degrada en silencio (log de warning): la
incidencia ya quedó persistida y visible en el portal admin.
"""

import logging

from platform.features.support.incidents.incident.domain.interfaces import IIncidentNotifier
from platform.features.support.incidents.incident.domain.schemas import IncidentView

logger = logging.getLogger('app.api')


class CeleryIncidentNotifier(IIncidentNotifier):

    def notify_created(self, incident: IncidentView) -> None:
        try:
            from platform.features.support.incidents.incident.tasks import notify_incident_created
            notify_incident_created.delay(incident.id)
        except Exception as exc:
            logger.warning('INCIDENT_NOTIFY_FAILED id=%s error=%s', incident.id, exc)
