"""
logging/facade/factory.py
─────────────────────────
Factory que resuelve las dependencias concretas del LogManager.

Uso:
    from client.features.logging.facade.factory import LogManagerFactory

    log = LogManagerFactory.create()
    log.audit(context, data)
"""

from client.features.logging.audit_trail.audit.infrastructure.repositories import DjangoAuditLogRepository
from client.features.logging.system.errors.infrastructure.handlers import FileErrorLogHandler
from client.features.logging.facade.events import InMemoryEventDispatcher
from client.features.logging.facade.manager import LogManager
from client.features.logging.ops.integration.infrastructure.repositories import DjangoIntegrationLogRepository
from client.features.logging.ops.operations.infrastructure.repositories import DjangoWarehouseEventRepository
from client.features.logging.system.performance.infrastructure.handlers import FilePerformanceLogHandler
from client.features.logging.security.security.infrastructure.repositories import DjangoSecurityLogRepository
from client.features.logging.system.system.infrastructure.handlers import FileSystemLogHandler


class LogManagerFactory:
    """Crea instancias de LogManager con las implementaciones concretas de infraestructura."""

    _event_dispatcher = None

    @classmethod
    def create(cls) -> LogManager:
        return LogManager(
            audit_repo=DjangoAuditLogRepository(),
            warehouse_repo=DjangoWarehouseEventRepository(),
            integration_repo=DjangoIntegrationLogRepository(),
            security_repo=DjangoSecurityLogRepository(),
            error_handler=FileErrorLogHandler(),
            performance_handler=FilePerformanceLogHandler(),
            system_handler=FileSystemLogHandler(),
            event_dispatcher=cls._get_event_dispatcher(),
        )

    @classmethod
    def _get_event_dispatcher(cls):
        if cls._event_dispatcher is None:
            cls._event_dispatcher = InMemoryEventDispatcher()
        return cls._event_dispatcher
