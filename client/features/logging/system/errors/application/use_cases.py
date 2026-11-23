from client.features.logging.system.errors.domain.interfaces import IErrorLogHandler
from client.features.logging.system.errors.domain.schemas import ErrorLogSchema
from client.features.logging.facade.context import LogContext
from core.trace import trace_layer


class RegisterErrorLogUseCase:
    def __init__(self, handler: IErrorLogHandler):
        self.handler = handler

    @trace_layer('application')
    def execute(self, context: LogContext, data: ErrorLogSchema) -> None:
        self.handler.emit(context, data)
