"""
Handlers de logs de eventos del sistema.

FileSystemLogHandler: usa el sistema de logging de Python (app.api).
"""

import logging

from client.features.logging.facade.context import LogContext
from client.features.logging.system.system.domain.interfaces import ISystemLogHandler
from client.features.logging.system.system.domain.schemas import SystemLogSchema

api_logger = logging.getLogger('app.api')

_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


class FileSystemLogHandler(ISystemLogHandler):
    """Emite logs de eventos del sistema al sistema de logging de Python."""

    def emit(self, context: LogContext, data: SystemLogSchema) -> None:
        log_level = _LEVEL_MAP.get(data.level.upper(), logging.INFO)

        api_logger.log(
            log_level,
            'SYSTEM_EVENT component=%s correlation_id=%s | %s',
            data.component,
            context.correlation_id or '-',
            data.message,
            extra={'trace_id': context.request_id, 'error_code': '-'},
        )
