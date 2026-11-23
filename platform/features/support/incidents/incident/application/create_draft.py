"""
CreateIncidentDraftUseCase — congela el material de una incidencia en el 500.

Arma el draft con la petición que falló + las últimas N peticiones del anillo
de la sesión, genera un token opaco y lo guarda en el draft store con TTL.

Puro respecto a Redis/Django: depende solo de los puertos ``ISessionLogBuffer``
e ``IIncidentDraftStore``. El token se genera con ``secrets`` (alta entropía).
"""

import secrets
from datetime import datetime, timezone

from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentDraftStore,
    ISessionLogBuffer,
)
from core.trace import trace_layer


class CreateIncidentDraftUseCase:

    def __init__(self, buffer: ISessionLogBuffer, draft_store: IIncidentDraftStore):
        self._buffer = buffer
        self._draft_store = draft_store

    @trace_layer('application')
    def execute(
        self,
        session_id: str,
        *,
        failed_request: dict,
        error: dict,
        frontend_logs=None,
    ) -> str:
        """Crea y persiste el draft. Devuelve el token (o '' si no hay sesión)."""
        if not session_id:
            return ''

        token = secrets.token_urlsafe(32)
        draft = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'session_id': session_id,
            'error': error,
            'failed_request': failed_request,
            'last_transactions': self._buffer.snapshot(session_id),
            'frontend_logs': list(frontend_logs or []),
        }
        self._draft_store.save(token, draft)
        return token
