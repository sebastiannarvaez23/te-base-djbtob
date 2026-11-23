from django.db import models

from core.ids import uuid7


class FeatureFlag(models.Model):
    """Release flag administrada en schema público."""

    FLAG_TYPE_CHOICES = [
        ('RELEASE', 'Release'),
        ('OPS', 'Ops'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('CERTIFIED', 'Certified'),
        ('DISABLED', 'Disabled'),
        ('ARCHIVED', 'Archived'),
    ]

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    key = models.CharField(
        max_length=100, unique=True, verbose_name='Key',
        help_text='Machine-readable identifier (e.g. picking.route_v2).',
    )
    name = models.CharField(max_length=120, verbose_name='Name')
    description = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Description',
    )
    flag_type = models.CharField(
        max_length=20, choices=FLAG_TYPE_CHOICES, default='RELEASE',
        verbose_name='Flag type',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='DRAFT',
        verbose_name='Status',
    )
    enabled = models.BooleanField(default=False, verbose_name='Enabled')
    owner = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Owner',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'release_feature_flags'
        verbose_name = 'Feature flag'
        verbose_name_plural = 'Feature flags'
        ordering = ['key']

    def __str__(self):
        return f'{self.key} ({self.status})'


class FeatureFlagScope(models.Model):
    """Target de liberación de una feature flag."""

    SCOPE_TYPE_CHOICES = [
        ('COMPANY', 'Company'),
        ('USER', 'User'),
        ('COUNTRY', 'Country'),
        ('STATE', 'State'),
        ('CITY', 'City'),
    ]

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.DO_NOTHING,
        related_name='scopes',
        verbose_name='Feature flag',
    )
    scope_type = models.CharField(
        max_length=20, choices=SCOPE_TYPE_CHOICES, verbose_name='Scope type',
    )
    scope_value = models.CharField(max_length=255, verbose_name='Scope value')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        db_table = 'release_feature_flag_scopes'
        verbose_name = 'Feature flag scope'
        verbose_name_plural = 'Feature flag scopes'
        ordering = ['scope_type', 'scope_value']

    def __str__(self):
        return f'{self.scope_type}={self.scope_value}'
