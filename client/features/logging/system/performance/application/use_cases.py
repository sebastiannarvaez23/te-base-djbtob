from client.features.logging.facade.context import LogContext
from client.features.logging.system.performance.domain.interfaces import IPerformanceLogHandler
from client.features.logging.system.performance.domain.schemas import PerformanceLogSchema
from core.trace import trace_layer


class RegisterPerformanceLogUseCase:
    def __init__(self, handler: IPerformanceLogHandler):
        self.handler = handler

    @trace_layer('application')
    def execute(self, context: LogContext, data: PerformanceLogSchema) -> None:
        self.handler.emit(context, data)
