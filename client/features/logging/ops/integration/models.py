from django.db import models

from core.ids import uuid7


class IntegrationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    system = models.CharField(max_length=100, verbose_name="Sistema externo")
    direction = models.CharField(max_length=20, verbose_name="Dirección")
    endpoint = models.CharField(max_length=500, verbose_name="Endpoint")
    method = models.CharField(max_length=10, verbose_name="Método HTTP")
    request_body = models.JSONField(null=True, blank=True, verbose_name="Request body")
    response_body = models.JSONField(null=True, blank=True, verbose_name="Response body")
    status_code = models.IntegerField(null=True, blank=True, verbose_name="Código de estado")
    duration_ms = models.IntegerField(null=True, blank=True, verbose_name="Duración (ms)")
    error_message = models.TextField(null=True, blank=True, verbose_name="Mensaje de error")

    user_id = models.UUIDField(null=True, blank=True, verbose_name="ID de usuario")
    warehouse_id = models.UUIDField(null=True, blank=True, verbose_name="ID de warehouse")
    request_id = models.CharField(max_length=64, verbose_name="ID de request")
    correlation_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="ID de correlación")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        db_table = 'integration_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['system']),
            models.Index(fields=['direction']),
            models.Index(fields=['status_code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.direction} {self.system} {self.method} {self.endpoint}'
