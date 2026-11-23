"""
core/task_trace.py
------------------
Buffer de logs acotado a la ejecución de una tarea Celery.

Separado de ``core.trace`` (buffer HTTP por request) para que las incidencias
de tareas automatizadas solo lleven logs de la propia tarea, nunca el anillo
de sesión del cliente.
"""

from contextvars import ContextVar

_task_logs: ContextVar[list | None] = ContextVar('task_logs', default=None)
_task_meta: ContextVar[dict | None] = ContextVar('task_meta', default=None)

TASK_LOG_TRUNCATED = '… (buffer de logs de tarea truncado)'


def start_task_capture(*, task_id: str = '', task_name: str = '', schema_name: str = '') -> None:
    """Inicia captura de logs para la tarea en curso."""
    _task_logs.set([])
    _task_meta.set({
        'task_id': task_id or '',
        'task_name': task_name or '',
        'schema_name': schema_name or '',
    })


def is_task_capturing() -> bool:
    return _task_logs.get() is not None


def get_task_meta() -> dict:
    return dict(_task_meta.get() or {})


def append_task_log(line: str, max_lines: int) -> None:
    buf = _task_logs.get()
    if buf is None:
        return
    count = len(buf)
    if count < max_lines:
        buf.append(line)
    elif count == max_lines:
        buf.append(TASK_LOG_TRUNCATED)


def peek_task_logs() -> list:
    buf = _task_logs.get()
    return list(buf) if buf is not None else []


def drain_task_logs() -> list:
    buf = _task_logs.get()
    _task_logs.set(None)
    _task_meta.set(None)
    return buf or []
