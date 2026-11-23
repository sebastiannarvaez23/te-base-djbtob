"""OAuth / Integration Application models (tenant schema)."""
from __future__ import annotations


from django.db import models

from core.ids import uuid7


class IntegrationApplicationStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    DISABLED = 'DISABLED', 'Disabled'
    REVOKED = 'REVOKED', 'Revoked'


class IntegrationApplicationEnvironment(models.TextChoices):
    CLIENT_TEST = 'CLIENT_TEST', 'Client test'
    CLIENT_PROD = 'CLIENT_PROD', 'Client production'


class IntegrationApplication(models.Model):
    """External application registered by the tenant to call the base APIs."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    client_id = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=IntegrationApplicationStatus.choices,
        default=IntegrationApplicationStatus.ACTIVE,
        db_index=True,
    )
    environment = models.CharField(
        max_length=20,
        choices=IntegrationApplicationEnvironment.choices,
        default=IntegrationApplicationEnvironment.CLIENT_TEST,
    )
    created_by = models.UUIDField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'integrations'
        db_table = 'integration_applications'
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.client_id})'


class IntegrationApplicationSecret(models.Model):
    """Hashed client_secret versions for an Integration Application."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    application = models.ForeignKey(
        IntegrationApplication,
        on_delete=models.DO_NOTHING,
        related_name='secrets',
    )
    secret_hash = models.CharField(max_length=128)
    secret_prefix = models.CharField(max_length=12, blank=True, default='')
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'integrations'
        db_table = 'integration_application_secrets'
        ordering = ['-version']
        indexes = [
            models.Index(fields=['application', 'is_active']),
        ]


class IntegrationApplicationScope(models.Model):
    """Scope granted to an Integration Application (least privilege)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    application = models.ForeignKey(
        IntegrationApplication,
        on_delete=models.DO_NOTHING,
        related_name='granted_scopes',
    )
    scope = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'integrations'
        db_table = 'integration_application_scopes'
        unique_together = [('application', 'scope')]
        ordering = ['scope']
