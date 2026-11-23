from client.features.logging.audit_trail.audit.domain.interfaces import IAuditLogRepository
from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema
from client.features.logging.facade.context import LogContext
from core.trace import trace_layer


class RegisterAuditLogUseCase:
    def __init__(self, repository: IAuditLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, context: LogContext, data: AuditLogInputSchema) -> None:
        self.repository.save(context, data)


class QueryAuditLogsUseCase:
    def __init__(self, repository: IAuditLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        return self.repository.query(filters, limit, offset)
