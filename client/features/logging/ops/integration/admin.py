from django.contrib import admin
from client.features.logging.ops.integration.models import IntegrationLog


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ('system', 'direction', 'method', 'endpoint', 'status_code', 'duration_ms', 'created_at')
    list_filter = ('system', 'direction', 'status_code', 'created_at')
    search_fields = ('endpoint', 'request_id', 'error_message')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
