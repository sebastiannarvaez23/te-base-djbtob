from django.db import models

from core.ids import uuid7


class TenantSecret(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    ciphertext = models.BinaryField(verbose_name='Ciphertext')
    key_version = models.PositiveIntegerField(default=1, verbose_name='Key version')
    rotated_at = models.DateTimeField(auto_now=True, verbose_name='Rotated at')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_tenant_secrets'


class IntegrationConnection(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('DEGRADED', 'Degraded'),
        ('ERROR', 'Error'),
    ]
    ENV_CHOICES = [
        ('PROSANDBOX', 'ProSandbox'),
        ('CLIENT_TEST', 'Client test'),
        ('CLIENT_PROD', 'Client production'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connector_key = models.CharField(max_length=50, verbose_name='Connector key')
    name = models.CharField(max_length=120, verbose_name='Name')
    environment = models.CharField(max_length=20, choices=ENV_CHOICES, verbose_name='Environment')
    config = models.JSONField(default=dict, verbose_name='Config')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    secret = models.ForeignKey(
        TenantSecret, on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='connections',
    )
    schedule_cron = models.CharField(max_length=64, blank=True, default='')
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    created_by = models.IntegerField(null=True, blank=True, verbose_name='User id')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_connections'
        ordering = ['name']


class FieldMapping(models.Model):
    DIRECTION_CHOICES = [
        ('INBOUND', 'Inbound'),
        ('OUTBOUND', 'Outbound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.DO_NOTHING, related_name='mappings',
    )
    entity = models.CharField(max_length=50, default='order')
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    rules = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_field_mappings'
        unique_together = [('connection', 'entity', 'direction')]


class SyncRun(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('SUCCESS', 'Success'),
        ('PARTIAL', 'Partial'),
        ('FAILED', 'Failed'),
    ]
    DIRECTION_CHOICES = [
        ('PULL', 'Pull'),
        ('PUSH', 'Push'),
        ('BIDIRECTIONAL', 'Bidirectional'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.DO_NOTHING, related_name='sync_runs',
    )
    entity = models.CharField(max_length=50, default='order')
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    stats = models.JSONField(default=dict)
    dry_run = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_sync_runs'
        ordering = ['-created_at']


class SyncOutbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.DO_NOTHING, related_name='outbox_items',
    )
    entity = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_sync_outbox'


class SyncInbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.DO_NOTHING, related_name='inbox_items',
    )
    external_id = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_sync_inbox'


class IntegrationOrder(models.Model):
    """Stub de pedidos hasta que exista client/features/warehouse/orders."""

    SYNC_STATUS_CHOICES = [
        ('SYNCED', 'Synced'),
        ('PENDING_OUTBOUND', 'Pending outbound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.DO_NOTHING, related_name='orders',
    )
    external_id = models.CharField(max_length=128)
    reference = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=50, default='DRAFT')
    payload = models.JSONField(default=dict)
    sync_status = models.CharField(max_length=30, choices=SYNC_STATUS_CHOICES, default='SYNCED')
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_orders'
        unique_together = [('connection', 'external_id')]


# OAuth Integration Applications (external apps → the base APIs)
from client.features.integrations.oauth.client.models import (  # noqa: E402,F401
    IntegrationApplication,
    IntegrationApplicationEnvironment,
    IntegrationApplicationScope,
    IntegrationApplicationSecret,
    IntegrationApplicationStatus,
)
