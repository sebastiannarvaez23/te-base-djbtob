from client.features.logging.facade.context import LogContext
from client.features.logging.ops.integration.domain.interfaces import IIntegrationLogRepository
from client.features.logging.ops.integration.domain.schemas import IntegrationLogInputSchema
from core.trace import trace_layer


class RegisterIntegrationLogUseCase:
    def __init__(self, repository: IIntegrationLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, context: LogContext, data: IntegrationLogInputSchema) -> None:
        self.repository.save(context, data)


class QueryIntegrationLogsUseCase:
    def __init__(self, repository: IIntegrationLogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        return self.repository.query(filters, limit, offset)
