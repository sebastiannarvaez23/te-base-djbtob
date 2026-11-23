"""
ReportTaskFailureUseCase — materializa una incidencia desde el fallo de una
tarea Celery, usando únicamente los logs capturados de esa ejecución.
"""

import logging
from datetime import datetime, timezone

from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentCreate, IncidentView
from core.trace import trace_layer

logger = logging.getLogger('app.tasks')

# Evita recursión: el notify post-incidencia no debe generar otra incidencia.
EXCLUDED_TASK_NAMES = frozenset({
    'incident.notify_created',
})


def _redact_task_log_line(line: str) -> str:
    """Best-effort PII/secret redaction for task log lines stored on incidents."""
    import re

    from core.logging_redaction import inline_json

    text = line or ''
    stripped = text.strip()
    if stripped.startswith('{') or stripped.startswith('['):
        return inline_json(stripped)
    return re.sub(
        r'(?i)\b(password|token|secret|authorization|api_key|refresh|access)\s*[:=]\s*\S+',
        r'\1=***',
        text,
    )


class ReportTaskFailureUseCase:

    def __init__(
        self,
        repository: IIncidentRepository,
        notifier: IIncidentNotifier,
    ):
        self._repo = repository
        self._notifier = notifier

    @trace_layer('application')
    def execute(
        self,
        *,
        task_id: str,
        task_name: str,
        exc: BaseException,
        traceback_text: str = '',
        task_logs: list[str] | None = None,
        schema_name: str = '',
    ) -> IncidentView | None:
        if not task_id or task_name in EXCLUDED_TASK_NAMES:
            return None

        token = f'task-{task_id}'
        existing = self._repo.get_by_token(token)
        if existing is not None:
            return existing

        logs = [
            _redact_task_log_line(line)
            for line in list(task_logs or [])
        ]
        now = datetime.now(timezone.utc).isoformat()
        exc_type = type(exc).__name__
        exc_msg = _redact_task_log_line(str(exc)[:2000])

        data = IncidentCreate(
            token=token,
            trace_id=task_id,
            severity='high',
            schema_name=schema_name or '',
            company_id='',
            reporter_user_id='system',
            reporter_username='celery',
            reporter_email='',
            page_section='automated_task',
            error={
                'code': 'TASK_FAIL',
                'exception_type': exc_type,
                'message': exc_msg,
                'traceback': (traceback_text or '')[:20000],
                'task_name': task_name,
                'task_id': task_id,
                'path': task_name,
                'method': 'TASK',
            },
            snapshot={
                'source': 'automated_task',
                'failed_request': {
                    'request_id': task_id,
                    'ts': now,
                    'origin': 'celery',
                    'method': 'TASK',
                    'path': task_name,
                    'query': None,
                    'request_body': '-',
                    'status': 500,
                    'response_body': '-',
                    'duration_ms': None,
                    'logs': logs,
                    'module_id': '',
                    'functionality_id': '',
                    'page_section': 'automated_task',
                },
                # Sin anillo HTTP: solo evidencia de la tarea.
                'last_transactions': [],
                'task': {
                    'id': task_id,
                    'name': task_name,
                    'schema_name': schema_name or '',
                },
            },
            user_comment=f'Fallo automático de tarea {task_name}',
        )

        try:
            incident = self._repo.create(data)
        except Exception:
            existing = self._repo.get_by_token(token)
            if existing is not None:
                return existing
            raise

        try:
            self._notifier.notify_created(incident)
        except Exception as notify_exc:
            logger.warning(
                'INCIDENT_NOTIFY_DISPATCH_FAILED code=%s error=%s',
                incident.code, notify_exc,
            )
        return incident
