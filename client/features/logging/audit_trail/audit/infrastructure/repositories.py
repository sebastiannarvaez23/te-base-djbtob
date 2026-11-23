from client.features.logging.audit_trail.audit.domain.interfaces import IAuditLogRepository
from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema
from client.features.logging.facade.context import LogContext


class DjangoAuditLogRepository(IAuditLogRepository):

    def save(self, context: LogContext, data: AuditLogInputSchema) -> None:
        from client.features.logging.audit_trail.audit.models import AuditLog
        AuditLog.objects.create(
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            action=data.action,
            changes=data.changes,
            description=data.description,
            user_id=context.user_id,
            warehouse_id=context.warehouse_id,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )

    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        from client.features.logging.audit_trail.audit.models import AuditLog
        qs = AuditLog.objects.all()
        if 'entity_type' in filters:
            qs = qs.filter(entity_type=filters['entity_type'])
        if 'entity_id' in filters:
            qs = qs.filter(entity_id=filters['entity_id'])
        if 'user_id' in filters:
            qs = qs.filter(user_id=filters['user_id'])
        if 'action' in filters:
            qs = qs.filter(action=filters['action'])
        if 'from_date' in filters:
            qs = qs.filter(created_at__gte=filters['from_date'])
        if 'to_date' in filters:
            qs = qs.filter(created_at__lte=filters['to_date'])
        return list(qs[offset:offset + limit])
