"""
logging/facade/manager.py
─────────────────────────
LogManager: punto de entrada único para registrar logs desde cualquier
parte de la aplicación.

Uso:
    from client.features.logging.facade.manager import LogManager

    log = LogManager()
    context = LogContextBuilder.from_request(request)
    log.audit(context, AuditLogInputSchema(...))
    log.warehouse_event(context, WarehouseEventInputSchema(...))
"""

import logging

from client.features.logging.audit_trail.audit.domain.interfaces import IAuditLogRepository
from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema
from client.features.logging.system.errors.domain.interfaces import IErrorLogHandler
from client.features.logging.system.errors.domain.schemas import ErrorLogSchema
from client.features.logging.facade.context import LogContext
from client.features.logging.facade.events import IDomainEventDispatcher
from client.features.logging.ops.integration.domain.interfaces import IIntegrationLogRepository
from client.features.logging.ops.integration.domain.schemas import IntegrationLogInputSchema
from client.features.logging.ops.operations.domain.interfaces import IWarehouseEventRepository
from client.features.logging.ops.operations.domain.schemas import WarehouseEventInputSchema
from client.features.logging.system.performance.domain.interfaces import IPerformanceLogHandler
from client.features.logging.system.performance.domain.schemas import PerformanceLogSchema
from client.features.logging.security.security.domain.interfaces import ISecurityLogRepository
from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema
from client.features.logging.system.system.domain.interfaces import ISystemLogHandler
from client.features.logging.system.system.domain.schemas import SystemLogSchema

logger = logging.getLogger('app.api')


class LogManager:
    """
    Facade central del sistema de logging.

    Recibe dependencias por constructor (Dependency Inversion).
    Cada método delega al repositorio/handler correspondiente y,
    cuando aplica, emite un evento de dominio.
    """

    def __init__(
        self,
        audit_repo: IAuditLogRepository,
        warehouse_repo: IWarehouseEventRepository,
        integration_repo: IIntegrationLogRepository,
        security_repo: ISecurityLogRepository,
        error_handler: IErrorLogHandler,
        performance_handler: IPerformanceLogHandler,
        system_handler: ISystemLogHandler,
        event_dispatcher: IDomainEventDispatcher = None,
    ):
        self._audit = audit_repo
        self._warehouse = warehouse_repo
        self._integration = integration_repo
        self._security = security_repo
        self._error = error_handler
        self._performance = performance_handler
        self._system = system_handler
        self._events = event_dispatcher

    # ── Logs persistidos en base de datos ────────────────────────────────

    def audit(self, context: LogContext, data: AuditLogInputSchema) -> None:
        """Registra una acción de auditoría sobre una entidad."""
        self._audit.save(context, data)

    def warehouse_event(self, context: LogContext, data: WarehouseEventInputSchema) -> None:
        """Registra un evento operativo del warehouse. Emite evento de dominio."""
        self._warehouse.save(context, data)
        if self._events:
            self._events.dispatch('warehouse_event', data)

    def integration(self, context: LogContext, data: IntegrationLogInputSchema) -> None:
        """Registra un evento de integración con sistemas externos."""
        self._integration.save(context, data)

    def security(self, context: LogContext, data: SecurityLogInputSchema) -> None:
        """Registra un evento de seguridad."""
        self._security.save(context, data)

    # ── Logs emitidos a sistemas externos ────────────────────────────────

    def error(self, context: LogContext, data: ErrorLogSchema) -> None:
        """Emite un log de error al sistema de logs (ELK / archivos)."""
        self._error.emit(context, data)

    def performance(self, context: LogContext, data: PerformanceLogSchema) -> None:
        """Emite métricas de performance al APM."""
        self._performance.emit(context, data)

    def system(self, context: LogContext, data: SystemLogSchema) -> None:
        """Emite un log de evento del sistema."""
        self._system.emit(context, data)
