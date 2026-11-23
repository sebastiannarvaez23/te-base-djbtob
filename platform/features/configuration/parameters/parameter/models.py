from django.db import models

from core.ids import uuid7


class Parameter(models.Model):
    """Global platform parameter with typed value."""

    DATA_TYPE_CHOICES = [
        ('STRING', 'String'),
        ('INT', 'Integer'),
        ('DECIMAL', 'Decimal'),
        ('BOOL', 'Boolean'),
        ('JSON', 'JSON'),
    ]

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    parameter_type = models.ForeignKey(
        'parameter_type.ParameterType', on_delete=models.DO_NOTHING,
        related_name='parameters', verbose_name='Parameter type',
    )
    code = models.CharField(
        max_length=20, unique=True, verbose_name='Unique code',
        help_text='Machine-readable identifier (e.g. MAX_LOGIN_RETRIES).',
    )
    name = models.CharField(
        max_length=30, verbose_name='Parameter name',
        help_text='Human-readable label shown in the admin UI.',
    )
    description = models.CharField(
        max_length=120, verbose_name='Description',
        blank=True, default='',
    )
    data_type = models.CharField(
        max_length=10, choices=DATA_TYPE_CHOICES, verbose_name='Data type',
        help_text='Type used to cast the stored value (STRING, INT, DECIMAL, BOOL, JSON).',
    )
    value = models.TextField(
        verbose_name='Value',
        help_text='Stored as text; cast at read time according to data_type.',
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Active',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'configuration_parameters'
        verbose_name = 'Parameter'
        verbose_name_plural = 'Parameters'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} ({self.data_type}) = {self.value}'
