"""
RedisIncidentDraftStore — almacén temporal del draft de incidencia.

Congela en el instante del 500 el snapshot (últimas N peticiones + la fallida +
error) bajo un token opaco, con TTL corto. El reporte lo consume una sola vez
(``GETDEL``): así un token filtrado solo sirve una vez y caduca solo.

Tolerante a fallos: cualquier error de Redis se traga (log de warning) para no
alterar la respuesta de error que el usuario está recibiendo.

⚠️ La garantía de un-solo-uso es ATÓMICA únicamente en Redis ≥ 6.2 (comando
``GETDEL``). En clientes/servidores anteriores se usa el fallback GET+DELETE,
que NO es atómico: dos lectores concurrentes del mismo token podrían ambos
obtener el draft antes del borrado. El despliegue objetivo debe correr Redis
6.2+ para que el single-use sea infalible.
"""

import json
import logging

from django.conf import settings

from platform.features.support.incidents.incident.domain.interfaces import IIncidentDraftStore

logger = logging.getLogger('app.api')

_KEY_PREFIX = 'incident_draft:'


def _get_client():
    """Cliente Redis crudo (import perezoso; los tests lo parchean)."""
    from django_redis import get_redis_connection
    return get_redis_connection('auth')


class RedisIncidentDraftStore(IIncidentDraftStore):

    def __init__(self):
        self._ttl = int(getattr(settings, 'INCIDENT_DRAFT_TTL_SECONDS', 3600))

    def save(self, token: str, draft: dict) -> None:
        if not token:
            return
        try:
            _get_client().setex(_KEY_PREFIX + token, self._ttl, json.dumps(draft, ensure_ascii=False))
        except Exception as exc:
            logger.warning('INCIDENT_DRAFT_SAVE_FAILED error=%s', exc)

    def pop(self, token: str):
        if not token:
            return None
        key = _KEY_PREFIX + token
        try:
            client = _get_client()
            # GETDEL (Redis 6.2+): lectura + borrado atómico (single-use).
            if callable(getattr(client, 'getdel', None)):
                raw = client.getdel(key)
            else:  # fallback para clientes antiguos
                raw = client.get(key)
                client.delete(key)
        except Exception as exc:
            logger.warning('INCIDENT_DRAFT_POP_FAILED error=%s', exc)
            return None

        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
