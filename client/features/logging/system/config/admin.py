from django.contrib import admin
from client.features.logging.system.config.models import LogConfiguration


@admin.register(LogConfiguration)
class LogConfigurationAdmin(admin.ModelAdmin):
    list_display = ('log_type', 'enabled', 'retention_days', 'archive_enabled', 'cleanup_frequency', 'updated_at')
    list_filter = ('enabled', 'cleanup_frequency')
    readonly_fields = ('id', 'updated_at')
