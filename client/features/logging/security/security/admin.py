from django.contrib import admin
from client.features.logging.security.security.models import SecurityLog


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user_id', 'target_user_id', 'ip_address', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('request_id', 'detail', 'ip_address')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
