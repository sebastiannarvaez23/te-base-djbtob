from client.features.logging.facade.context import LogContext
from client.features.logging.security.security.domain.interfaces import ISecurityLogRepository
from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema
from core.trace import trace_layer


class RegisterSecurityLogUseCase:
    def __init__(self, repository: ISecurityLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, context: LogContext, data: SecurityLogInputSchema) -> None:
        self.repository.save(context, data)


class QuerySecurityLogsUseCase:
    def __init__(self, repository: ISecurityLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        return self.repository.query(filters, limit, offset)
