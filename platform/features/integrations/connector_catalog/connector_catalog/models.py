from django.db import models

from core.ids import uuid7


class ConnectorDefinition(models.Model):
    """Catálogo global de conectores (schema public)."""

    KIND_CHOICES = [
        ('ERP', 'ERP'),
        ('PROVIDER', 'Provider'),
        ('APP', 'App'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    key = models.CharField(max_length=50, unique=True, verbose_name='Key')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name='Kind')
    name = models.CharField(max_length=120, verbose_name='Name')
    description = models.TextField(blank=True, default='', verbose_name='Description')
    version = models.CharField(max_length=20, default='1.0', verbose_name='Version')
    capabilities = models.JSONField(default=list, verbose_name='Capabilities')
    config_schema = models.JSONField(default=dict, verbose_name='Config schema')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_connector_definitions'
        ordering = ['key']

    def __str__(self):
        return f'{self.key} v{self.version}'
