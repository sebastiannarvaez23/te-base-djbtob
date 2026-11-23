"""
RedisSessionLogBuffer — anillo por sesión de las últimas N peticiones.

Implementado con una LIST de Redis por sesión:
    key = sess_txns:<session_id>
    LPUSH (nueva al frente) + LTRIM 0 N-1 (conserva solo N) + EXPIRE (TTL).

El acceso es tolerante a fallos: cualquier error de Redis se traga (log de
warning) para no romper ni frenar el request. Cada entrada se acota en tamaño
para que ni la memoria ni Redis crezcan sin límite.
"""

import json
import logging

from django.conf import settings

from platform.features.support.incidents.incident.domain.interfaces import ISessionLogBuffer
from platform.features.support.incidents.incident.domain.schemas import TransactionLogEntry

logger = logging.getLogger('app.api')

_KEY_PREFIX = 'sess_txns:'
_SHRINK_BODY_CHARS = 500
_ENTRY_TRUNCATED_MARK = '… (entrada truncada por tamaño)'


def _get_client():
    """Cliente Redis crudo (necesario para operaciones de LIST).

    Import perezoso: ``django_redis`` es dependencia solo de despliegue; los
    tests parchean esta función.
    """
    from django_redis import get_redis_connection
    return get_redis_connection('auth')


class RedisSessionLogBuffer(ISessionLogBuffer):

    def __init__(self):
        self._ring_size = int(getattr(settings, 'INCIDENT_RING_SIZE', 10))
        self._ttl = int(getattr(settings, 'INCIDENT_TXN_TTL_SECONDS', 3600))
        self._max_bytes = int(getattr(settings, 'INCIDENT_ENTRY_MAX_BYTES', 16384))

    def append_transaction(self, session_id: str, entry: TransactionLogEntry) -> None:
        if not session_id:
            return
        try:
            payload = self._serialize(entry)
            key = _KEY_PREFIX + session_id
            client = _get_client()
            pipe = client.pipeline()
            pipe.lpush(key, payload)
            pipe.ltrim(key, 0, self._ring_size - 1)
            pipe.expire(key, self._ttl)
            pipe.execute()
        except Exception as exc:
            logger.warning('SESSION_BUFFER_APPEND_FAILED sid=%s error=%s', session_id, exc)

    def snapshot(self, session_id: str) -> list[dict]:
        if not session_id:
            return []
        try:
            key = _KEY_PREFIX + session_id
            raw = _get_client().lrange(key, 0, self._ring_size - 1)
        except Exception as exc:
            logger.warning('SESSION_BUFFER_SNAPSHOT_FAILED sid=%s error=%s', session_id, exc)
            return []

        entries = []
        for item in raw:
            if isinstance(item, bytes):
                item = item.decode('utf-8', errors='replace')
            try:
                entries.append(json.loads(item))
            except (ValueError, TypeError):
                continue
        # LPUSH deja la más reciente al frente; se invierte a orden cronológico.
        entries.reverse()
        return entries

    # ── Serialización acotada ────────────────────────────────────────────

    def _serialize(self, entry: TransactionLogEntry) -> str:
        data = entry.model_dump()
        payload = json.dumps(data, ensure_ascii=False)
        if len(payload.encode('utf-8')) <= self._max_bytes:
            return payload
        return json.dumps(self._shrink(data), ensure_ascii=False)

    def _shrink(self, data: dict) -> dict:
        """Reduce una entrada que excede el tope: recorta bodies y logs.

        Serializa el 'sobre' (todo menos los logs) una sola vez y luego va
        agregando logs mientras quepan dentro del presupuesto, reservando
        espacio para el marcador de truncado. Es O(n) sobre los logs, en vez
        del O(n²) de re-serializar el dict completo tras cada ``pop()``.
        """
        for field in ('request_body', 'response_body'):
            value = data.get(field)
            if isinstance(value, str) and len(value) > _SHRINK_BODY_CHARS:
                data[field] = value[:_SHRINK_BODY_CHARS] + '…'

        original_logs = list(data.get('logs') or [])

        # Tamaño del sobre sin logs (una sola serialización).
        data['logs'] = []
        base_size = len(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        marker_size = len(
            json.dumps(_ENTRY_TRUNCATED_MARK, ensure_ascii=False).encode('utf-8')
        ) + 1  # +1 por el separador de lista

        kept: list = []
        size = base_size
        truncated = False
        for entry in original_logs:
            entry_size = len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) + 1
            if size + entry_size + marker_size > self._max_bytes:
                truncated = True
                break
            kept.append(entry)
            size += entry_size

        data['logs'] = kept + ([_ENTRY_TRUNCATED_MARK] if truncated else [])
        return data
