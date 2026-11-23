"""
Handlers de logs de error.

FileErrorLogHandler: usa el sistema de logging de Python (app.errors).
Reemplazar por ElkErrorLogHandler para envío directo a ELK/Datadog.
"""

import json
import logging

from client.features.logging.system.errors.domain.interfaces import IErrorLogHandler
from client.features.logging.system.errors.domain.schemas import ErrorLogSchema
from client.features.logging.facade.context import LogContext

error_logger = logging.getLogger('app.errors')


class FileErrorLogHandler(IErrorLogHandler):
    """Emite logs de error al sistema de logging de Python (archivos rotativos)."""

    def emit(self, context: LogContext, data: ErrorLogSchema) -> None:
        log_level = logging.CRITICAL if data.level == 'CRITICAL' else logging.ERROR

        error_logger.log(
            log_level,
            'ERROR_LOG request_id=%s error_code=%s exception=%s module=%s | %s',
            context.request_id,
            data.error_code or '-',
            data.exception_type,
            data.module or '-',
            data.message,
            extra={
                'trace_id': context.request_id,
                'error_code': data.error_code or '-',
            },
        )

        if data.stacktrace:
            error_logger.debug(
                'STACKTRACE request_id=%s\n%s',
                context.request_id,
                data.stacktrace,
            )


class ElkErrorLogHandler(IErrorLogHandler):
    """
    Emite logs de error a ELK via HTTP.

    Requiere configuración:
        ELK_ENDPOINT en settings o variable de entorno.
    """

    def __init__(self, endpoint: str = None):
        self.endpoint = endpoint

    def emit(self, context: LogContext, data: ErrorLogSchema) -> None:
        payload = {
            'timestamp': context.timestamp.isoformat(),
            'level': data.level,
            'error_code': data.error_code,
            'exception_type': data.exception_type,
            'message': data.message,
            'stacktrace': data.stacktrace,
            'module': data.module,
            'request_id': context.request_id,
            'user_id': context.user_id,
            'warehouse_id': context.warehouse_id,
            'correlation_id': context.correlation_id,
        }

        error_logger.info(
            'ELK_ERROR_LOG payload=%s',
            json.dumps(payload, default=str),
            extra={'trace_id': context.request_id, 'error_code': data.error_code or '-'},
        )
