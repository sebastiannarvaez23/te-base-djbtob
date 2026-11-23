"""
Tareas Celery del sistema de incidencias.

``incident.notify_created`` corre fuera del request (no añade latencia al
reporte). Emite una señal estructurada ``INCIDENT_CREATED`` al canal de errores
que ops observa. Punto de extensión: crear la campanita in-app para admins.
"""

import logging

from celery import shared_task

from core.tasks.base import BaseTask

logger = logging.getLogger('app.tasks')


@shared_task(base=BaseTask, name='incident.notify_created', bind=True)
def notify_incident_created(self, incident_id: str) -> None:
    from platform.features.support.incidents.incident.models import Incident

    inc = Incident.objects.filter(id=incident_id).first()
    if inc is None:
        return

    logging.getLogger('app.errors').warning(
        'INCIDENT_CREATED code=%s status=%s schema=%s reporter=%s trace_id=%s path=%s',
        inc.code, inc.status, inc.schema_name or '-', inc.reporter_username or '-',
        inc.trace_id or '-', (inc.error or {}).get('path', '-'),
        extra={'trace_id': inc.trace_id or '-'},
    )
    # TODO(Fase 4+): crear notificación in-app (campanita) para los admins.
