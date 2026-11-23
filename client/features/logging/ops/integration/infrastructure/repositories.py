from client.features.logging.facade.context import LogContext
from client.features.logging.ops.integration.domain.interfaces import IIntegrationLogRepository
from client.features.logging.ops.integration.domain.schemas import IntegrationLogInputSchema


class DjangoIntegrationLogRepository(IIntegrationLogRepository):

    def save(self, context: LogContext, data: IntegrationLogInputSchema) -> None:
        from client.features.logging.ops.integration.models import IntegrationLog
        IntegrationLog.objects.create(
            system=data.system,
            direction=data.direction,
            endpoint=data.endpoint,
            method=data.method,
            request_body=data.request_body,
            response_body=data.response_body,
            status_code=data.status_code,
            duration_ms=data.duration_ms,
            error_message=data.error_message,
            user_id=context.user_id,
            warehouse_id=context.warehouse_id,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            ip_address=context.ip_address,
        )

    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        from client.features.logging.ops.integration.models import IntegrationLog
        qs = IntegrationLog.objects.all()
        if 'system' in filters:
            qs = qs.filter(system=filters['system'])
        if 'direction' in filters:
            qs = qs.filter(direction=filters['direction'])
        if 'status_code' in filters:
            qs = qs.filter(status_code=filters['status_code'])
        if 'from_date' in filters:
            qs = qs.filter(created_at__gte=filters['from_date'])
        if 'to_date' in filters:
            qs = qs.filter(created_at__lte=filters['to_date'])
        return list(qs[offset:offset + limit])
