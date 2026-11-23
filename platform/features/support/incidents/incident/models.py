from django.db import models

from core.ids import uuid7


class Incident(models.Model):
    """Incidencia levantada cuando un usuario reporta un error 500.

    Vive en el schema público (SHARED_APP): es una preocupación administrativa
    transversal a todas las empresas. El ``snapshot`` es evidencia inmutable
    (las últimas peticiones + la fallida), congelada al momento del fallo.
    """

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_DISCARDED = 'discarded'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Abierta'),
        (STATUS_IN_PROGRESS, 'En progreso'),
        (STATUS_RESOLVED, 'Resuelta'),
        (STATUS_CLOSED, 'Cerrada'),
        (STATUS_DISCARDED, 'Descartada'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ]

    KIND_INCIDENT = 'incident'
    KIND_SUGGESTION = 'suggestion'
    KIND_CHOICES = [
        (KIND_INCIDENT, 'Incidencia'),
        (KIND_SUGGESTION, 'Sugerencia'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='Código')
    token = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_INCIDENT)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='high')

    schema_name = models.CharField(max_length=63, blank=True, default='')
    company_id = models.CharField(max_length=64, blank=True, default='')

    reporter_user_id = models.CharField(max_length=64, blank=True, default='')
    reporter_username = models.CharField(max_length=150, blank=True, default='')
    reporter_email = models.CharField(max_length=254, blank=True, default='')

    trace_id = models.CharField(max_length=64, blank=True, default='')

    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Módulo',
    )
    functionality = models.ForeignKey(
        'functionalities.Functionality',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Funcionalidad',
    )
    # Apartado de la página dentro del módulo (p.ej. profile, company, users).
    page_section = models.CharField(max_length=63, blank=True, default='', verbose_name='Apartado')

    error = models.JSONField(default=dict)
    snapshot = models.JSONField(default=dict)
    user_comment = models.TextField(blank=True, default='')
    # Metadatos de evidencia en MinIO (bucket de incidencias); los bytes no viven en la BD.
    attachments = models.JSONField(default=list, blank=True)

    assigned_admin_id = models.CharField(max_length=64, blank=True, default='')
    resolution_notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'incidents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['kind'], name='incidents_kind_idx'),
            models.Index(fields=['schema_name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.code} ({self.status})'
