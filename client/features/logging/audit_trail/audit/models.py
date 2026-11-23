from django.db import models

from core.ids import uuid7


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    entity_type = models.CharField(max_length=100, verbose_name="Tipo de entidad")
    entity_id = models.CharField(max_length=100, verbose_name="ID de entidad")
    action = models.CharField(max_length=50, verbose_name="Acción")
    changes = models.JSONField(null=True, blank=True, verbose_name="Cambios")
    description = models.TextField(null=True, blank=True, verbose_name="Descripción")

    user_id = models.UUIDField(null=True, blank=True, verbose_name="ID de usuario")
    warehouse_id = models.UUIDField(null=True, blank=True, verbose_name="ID de warehouse")
    request_id = models.CharField(max_length=64, verbose_name="ID de request")
    correlation_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="ID de correlación")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User Agent")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f'{self.action} {self.entity_type}:{self.entity_id}'
