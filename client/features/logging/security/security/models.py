from django.db import models

from core.ids import uuid7


class SecurityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    event_type = models.CharField(max_length=50, verbose_name="Tipo de evento")
    target_user_id = models.UUIDField(null=True, blank=True, verbose_name="ID de usuario objetivo")
    resource = models.CharField(max_length=200, null=True, blank=True, verbose_name="Recurso")
    detail = models.TextField(null=True, blank=True, verbose_name="Detalle")

    user_id = models.UUIDField(null=True, blank=True, verbose_name="ID de usuario")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User Agent")
    request_id = models.CharField(max_length=64, verbose_name="ID de request")
    correlation_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="ID de correlación")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        db_table = 'security_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['user_id']),
            models.Index(fields=['target_user_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f'{self.event_type} user={self.user_id}'
