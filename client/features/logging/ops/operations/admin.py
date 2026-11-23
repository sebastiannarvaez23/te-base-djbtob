from django.contrib import admin
from client.features.logging.ops.operations.models import WarehouseEvent


@admin.register(WarehouseEvent)
class WarehouseEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'zone', 'location', 'warehouse_id', 'created_at')
    list_filter = ('event_type', 'zone', 'created_at')
    search_fields = ('reference_id', 'request_id')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
