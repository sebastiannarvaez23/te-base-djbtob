from django.db import models

from core.ids import uuid7


class LogConfiguration(models.Model):
    """Configuración de retención y habilitación por tipo de log. Administrable desde la plataforma."""

    LOG_TYPE_CHOICES = [
        ('audit', 'Auditoría'),
        ('operations', 'Operaciones'),
        ('integration', 'Integración'),
        ('security', 'Seguridad'),
        ('errors', 'Errores'),
        ('performance', 'Performance'),
        ('system', 'Sistema'),
        ('tenant', 'Logs por empresa'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    log_type = models.CharField(max_length=50, unique=True, choices=LOG_TYPE_CHOICES, verbose_name="Tipo de log")
    enabled = models.BooleanField(default=True, verbose_name="Habilitado")
    retention_days = models.IntegerField(default=90, verbose_name="Días de retención")
    archive_enabled = models.BooleanField(default=False, verbose_name="Archivado habilitado")
    archive_after_days = models.IntegerField(null=True, blank=True, default=60, verbose_name="Archivar después de (días)")
    max_records = models.IntegerField(null=True, blank=True, verbose_name="Máximo de registros")
    cleanup_frequency = models.CharField(max_length=20, default='daily', choices=FREQUENCY_CHOICES, verbose_name="Frecuencia de limpieza")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        db_table = 'log_configurations'
        ordering = ['log_type']

    def __str__(self):
        return f'{self.log_type} (retention={self.retention_days}d, enabled={self.enabled})'
