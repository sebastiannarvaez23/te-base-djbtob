from django.contrib import admin
from client.features.logging.audit_trail.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'entity_type', 'entity_id', 'user_id', 'created_at')
    list_filter = ('action', 'entity_type', 'created_at')
    search_fields = ('entity_id', 'request_id', 'description')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
