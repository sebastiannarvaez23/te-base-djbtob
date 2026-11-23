"""
Handlers de logs de performance.

FilePerformanceLogHandler: usa el sistema de logging de Python (app.api).
Reemplazar por ApmPerformanceLogHandler para envío a Datadog/NewRelic/etc.
"""

import json
import logging

from client.features.logging.facade.context import LogContext
from client.features.logging.system.performance.domain.interfaces import IPerformanceLogHandler
from client.features.logging.system.performance.domain.schemas import PerformanceLogSchema

api_logger = logging.getLogger('app.api')


class FilePerformanceLogHandler(IPerformanceLogHandler):
    """Emite métricas de performance al sistema de logging de Python."""

    def emit(self, context: LogContext, data: PerformanceLogSchema) -> None:
        api_logger.info(
            'PERFORMANCE request_id=%s operation=%s duration_ms=%d endpoint=%s '
            'method=%s db_queries=%s memory_mb=%s',
            context.request_id,
            data.operation,
            data.duration_ms,
            data.endpoint or '-',
            data.method or '-',
            data.db_queries if data.db_queries is not None else '-',
            data.memory_mb if data.memory_mb is not None else '-',
            extra={'trace_id': context.request_id, 'error_code': '-'},
        )


class ApmPerformanceLogHandler(IPerformanceLogHandler):
    """
    Emite métricas de performance a un APM externo.

    Requiere configuración:
        APM_ENDPOINT en settings o variable de entorno.
    """

    def __init__(self, endpoint: str = None):
        self.endpoint = endpoint

    def emit(self, context: LogContext, data: PerformanceLogSchema) -> None:
        payload = {
            'timestamp': context.timestamp.isoformat(),
            'operation': data.operation,
            'duration_ms': data.duration_ms,
            'endpoint': data.endpoint,
            'method': data.method,
            'db_queries': data.db_queries,
            'memory_mb': data.memory_mb,
            'tags': data.tags,
            'request_id': context.request_id,
            'user_id': context.user_id,
            'warehouse_id': context.warehouse_id,
        }

        api_logger.info(
            'APM_PERFORMANCE payload=%s',
            json.dumps(payload, default=str),
            extra={'trace_id': context.request_id, 'error_code': '-'},
        )
