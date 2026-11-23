"""Disparador del fan-out vía Celery (desacoplado por nombre de tarea).

La plataforma nunca importa código del mundo tenant: encola la tarea
``inbox.process_outbox_fanout`` por su nombre registrado. El worker (que sí
vive en ``client``) la ejecuta y materializa las notificaciones por schema.
"""

import uuid

from platform.features.communication.messaging.inbox.domain.interfaces import IOutboxDispatchTrigger

FANOUT_TASK_NAME = 'inbox.process_outbox_fanout'


class CeleryOutboxDispatchTrigger(IOutboxDispatchTrigger):

    def trigger(self, outbox_id: uuid.UUID) -> None:
        from core.tasks.app import app as celery_app
        celery_app.send_task(FANOUT_TASK_NAME, args=[str(outbox_id)])
