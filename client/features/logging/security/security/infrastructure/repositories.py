from client.features.logging.facade.context import LogContext
from client.features.logging.security.security.domain.interfaces import ISecurityLogRepository
from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema


class DjangoSecurityLogRepository(ISecurityLogRepository):

    def save(self, context: LogContext, data: SecurityLogInputSchema) -> None:
        from client.features.logging.security.security.models import SecurityLog
        SecurityLog.objects.create(
            event_type=data.event_type,
            target_user_id=data.target_user_id,
            resource=data.resource,
            detail=data.detail,
            user_id=context.user_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
        )

    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        from client.features.logging.security.security.models import SecurityLog
        qs = SecurityLog.objects.all()
        if 'event_type' in filters:
            qs = qs.filter(event_type=filters['event_type'])
        if 'user_id' in filters:
            qs = qs.filter(user_id=filters['user_id'])
        if 'target_user_id' in filters:
            qs = qs.filter(target_user_id=filters['target_user_id'])
        if 'ip_address' in filters:
            qs = qs.filter(ip_address=filters['ip_address'])
        if 'from_date' in filters:
            qs = qs.filter(created_at__gte=filters['from_date'])
        if 'to_date' in filters:
            qs = qs.filter(created_at__lte=filters['to_date'])
        return list(qs[offset:offset + limit])
