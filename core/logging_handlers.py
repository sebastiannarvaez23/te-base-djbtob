"""
core/logging_handlers.py
------------------------
Handler de logging que enruta cada registro a la carpeta de la empresa
(tenant) que originó la petición, con un archivo por día.

Estructura resultante:
    logs/tenants/<schema_name>/<YYYY-MM-DD>.log

El schema del tenant se obtiene del ContextVar publicado por el
``RequestLoggingMiddleware`` (ver ``core.trace.set_tenant``). Los registros
sin tenant o del schema público (admin/landing) se ignoran silenciosamente:
esos siguen viviendo en los handlers compartidos (consola, app.log, etc.).
"""

import logging
import re
import sys
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path

from django.conf import settings

from core.trace import append_txn_log, get_tenant, get_trace_id, is_txn_capturing

# Defensivo: el schema_name ya es [a-z0-9-], pero sanitizamos por si acaso.
_UNSAFE = re.compile(r'[^A-Za-z0-9._-]')

# Buffers de consola indexados por trace_id (no ContextVar): bajo Daphne/ASGI
# el ContextVar a veces no está visible en ``emit``, pero el ``trace_id`` del
# LogRecord sí viaja en cada línea. OrderedDict para evicción FIFO si un
# request muere sin ``flush`` (worker kill / bug).
_CONSOLE_BUFFERS: OrderedDict[str, list[str]] = OrderedDict()
_CONSOLE_LOCK = threading.Lock()
_CONSOLE_MAX_BUFFERS = 256
_CONSOLE_MAX_LINES = 2000
_CONSOLE_BOUND_STREAM = None


class OrderedRequestConsoleHandler(logging.StreamHandler):
    """Consola de ``app.request`` con bloques ordenados por request.

    El middleware abre un buffer por ``trace_id``; cada ``emit`` anexa la
    línea formateada a ese buffer. Al cerrar el request se vuelca el bloque
    completo bajo lock (REQ → proceso → RES) para que requests concurrentes
    no intercalen líneas. Coste: lista en memoria + un write al final.
    """

    def __init__(self, stream=None):
        super().__init__(stream)
        global _CONSOLE_BOUND_STREAM
        _CONSOLE_BOUND_STREAM = self.stream

    def emit(self, record):
        try:
            msg = self.format(record)
            trace_id = self._resolve_trace_id(record)
            if trace_id != '-' and self._append(trace_id, msg):
                return
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    @staticmethod
    def _resolve_trace_id(record) -> str:
        trace_id = getattr(record, 'trace_id', None) or '-'
        if trace_id != '-':
            return str(trace_id)
        try:
            return get_trace_id() or '-'
        except Exception:
            return '-'

    @staticmethod
    def open_request(trace_id: str) -> None:
        if not trace_id or trace_id == '-':
            return
        with _CONSOLE_LOCK:
            # Evict oldest abandoned buffers if the process leaked them.
            while len(_CONSOLE_BUFFERS) >= _CONSOLE_MAX_BUFFERS:
                _CONSOLE_BUFFERS.popitem(last=False)
            _CONSOLE_BUFFERS[trace_id] = []
            _CONSOLE_BUFFERS.move_to_end(trace_id)

    @staticmethod
    def _append(trace_id: str, line: str) -> bool:
        with _CONSOLE_LOCK:
            buf = _CONSOLE_BUFFERS.get(trace_id)
            if buf is None:
                return False
            if len(buf) < _CONSOLE_MAX_LINES:
                buf.append(line)
            elif len(buf) == _CONSOLE_MAX_LINES:
                buf.append('… (console buffer truncated)')
            return True

    @classmethod
    def flush_request(cls, trace_id: str, stream=None) -> None:
        """Vuelca y elimina el buffer del ``trace_id`` de forma atómica."""
        if not trace_id or trace_id == '-':
            return
        with _CONSOLE_LOCK:
            lines = _CONSOLE_BUFFERS.pop(trace_id, None)
            if not lines:
                return
            out = stream
            if out is None:
                out = _CONSOLE_BOUND_STREAM if _CONSOLE_BOUND_STREAM is not None else sys.stderr
            parts = []
            for line in lines:
                parts.append(line if line.endswith('\n') else line + '\n')
            # Línea en blanco al final de cada request para separar bloques.
            block = ''.join(parts).rstrip('\n') + '\n\n'
            out.write(block)
            out.flush()


class BufferingLogHandler(logging.Handler):
    """Acumula en memoria las líneas de log internas de la petición en curso.

    Cada record formateado se anexa al buffer de la transacción (contextvar en
    ``core.trace``), que luego el middleware drena para armar la entrada de la
    petición en el sistema de incidencias. Fuera de un request (sin captura
    activa) no hace nada. El tope de líneas evita cualquier crecimiento
    descontrolado de memoria.

    Omite el sobre HTTP (``>> REQ`` / ``<< RES``): esos datos viven en
    ``request_body`` / ``response_body`` / método / path de la entrada.
    """

    _SKIP_MSG_PREFIXES = ('>> REQ', '<< RES')

    def __init__(self, max_lines: int = None):
        super().__init__()
        self._max_lines = max_lines

    @property
    def max_lines(self) -> int:
        if self._max_lines is None:
            self._max_lines = int(getattr(settings, 'INCIDENT_MAX_LOGS_PER_TXN', 200))
        return self._max_lines

    def emit(self, record):
        try:
            if not is_txn_capturing():
                return
            message = record.getMessage()
            if message.startswith(self._SKIP_MSG_PREFIXES):
                return
            append_txn_log(self.format(record), self.max_lines)
        except Exception:
            self.handleError(record)


class TaskBufferingLogHandler(logging.Handler):
    """Acumula logs solo mientras corre una tarea Celery con captura activa.

    Pensado para el logger ``app.tasks``: las incidencias de fallos
    automatizados llevan únicamente estas líneas (no el anillo HTTP).
    """

    def __init__(self, max_lines: int = None):
        super().__init__()
        self._max_lines = max_lines

    @property
    def max_lines(self) -> int:
        if self._max_lines is None:
            self._max_lines = int(getattr(settings, 'INCIDENT_MAX_LOGS_PER_TXN', 200))
        return self._max_lines

    def emit(self, record):
        try:
            from core.task_trace import append_task_log, is_task_capturing
            if not is_task_capturing():
                return
            append_task_log(self.format(record), self.max_lines)
        except Exception:
            self.handleError(record)


class TenantDailyFileHandler(logging.Handler):
    """Escribe cada log en ``<base_dir>/<schema>/<YYYY-MM-DD>.log``.

    Abre un archivo por empresa y por día de forma perezosa y lo cachea.
    Cuando cambia el día, rota al archivo nuevo automáticamente. ``emit`` se
    ejecuta bajo el lock del handler (``logging.Handler.handle``), de modo que
    el acceso a la caché de streams está serializado.
    """

    terminator = '\n'

    def __init__(self, base_dir=None, encoding='utf-8'):
        super().__init__()
        self.base_dir = Path(base_dir or getattr(settings, 'TENANT_LOGS_DIR'))
        self.encoding = encoding
        self._public = getattr(settings, 'PUBLIC_SCHEMA_NAME', 'public')
        self._streams: dict[str, tuple[str, object]] = {}  # schema -> (día, stream)
        self._close_lock = threading.Lock()

    def emit(self, record):
        try:
            schema = get_tenant()
            if not schema or schema == self._public:
                return
            stream = self._get_stream(schema)
            stream.write(self.format(record) + self.terminator)
            stream.flush()
        except Exception:
            self.handleError(record)

    def _get_stream(self, schema):
        today = date.today().isoformat()
        cached = self._streams.get(schema)
        if cached and cached[0] == today:
            return cached[1]

        # Día nuevo (o primer log de la empresa): cerrar el anterior y abrir hoy.
        if cached:
            try:
                cached[1].close()
            except Exception:
                pass

        folder = self.base_dir / (_UNSAFE.sub('_', schema) or 'unknown')
        folder.mkdir(parents=True, exist_ok=True)
        stream = open(folder / f'{today}.log', 'a', encoding=self.encoding)
        self._streams[schema] = (today, stream)
        return stream

    def close(self):
        with self._close_lock:
            for _, stream in self._streams.values():
                try:
                    stream.close()
                except Exception:
                    pass
            self._streams.clear()
        super().close()
