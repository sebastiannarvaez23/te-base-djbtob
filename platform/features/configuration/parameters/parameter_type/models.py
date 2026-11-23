from django.db import models

from core.ids import uuid7


class ParameterType(models.Model):
    """Category for grouping related parameters (e.g. SECURITY, BILLING)."""

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    code = models.CharField(
        max_length=20, unique=True, verbose_name='Unique code',
        help_text='Machine-readable identifier (e.g. SECURITY, BILLING).',
    )
    name = models.CharField(
        max_length=30, verbose_name='Type name',
        help_text='Human-readable label shown in the admin UI.',
    )
    description = models.CharField(
        max_length=120, verbose_name='Description',
        blank=True, default='',
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Active',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'configuration_parameter_types'
        verbose_name = 'Parameter type'
        verbose_name_plural = 'Parameter types'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'
