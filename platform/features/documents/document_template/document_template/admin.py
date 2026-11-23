from django.contrib import admin
from .models import DocumentTemplate


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'kind', 'default_format', 'is_storable', 'is_active', 'updated_at')
    list_filter = ('kind', 'is_active', 'is_storable', 'default_format')
    search_fields = ('code', 'name', 'kind', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Identity', {
            'fields': ('id', 'code', 'name', 'kind', 'description', 'is_active'),
        }),
        ('HTML body', {
            'fields': ('html_template', 'mock_data'),
        }),
        ('Formats', {
            'fields': ('allowed_formats', 'default_format', 'format_configs'),
        }),
        ('Storage', {
            'fields': ('is_storable', 'storage_bucket', 'storage_path_template'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
