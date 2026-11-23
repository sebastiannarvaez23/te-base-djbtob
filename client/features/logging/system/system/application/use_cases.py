from client.features.logging.facade.context import LogContext
from client.features.logging.system.system.domain.interfaces import ISystemLogHandler
from client.features.logging.system.system.domain.schemas import SystemLogSchema
from core.trace import trace_layer


class RegisterSystemLogUseCase:
    def __init__(self, handler: ISystemLogHandler):
        self.handler = handler

    @trace_layer('application')
    def execute(self, context: LogContext, data: SystemLogSchema) -> None:
        self.handler.emit(context, data)
