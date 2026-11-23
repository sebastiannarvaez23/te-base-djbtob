from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q

from client.features.logging.ops.operations.domain.schemas import RECENT_ACTIVITY_EVENT_TYPES
from core.ids import uuid7


class WarehouseEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    event_type = models.CharField(max_length=50, verbose_name="Tipo de evento")
    zone = models.CharField(max_length=50, null=True, blank=True, verbose_name="Zona")
    location = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ubicación")
    reference_type = models.CharField(max_length=100, null=True, blank=True, verbose_name="Tipo de referencia")
    reference_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID de referencia")
    payload = models.JSONField(null=True, blank=True, verbose_name="Datos adicionales")

    user_id = models.UUIDField(null=True, blank=True, verbose_name="ID de usuario")
    warehouse_id = models.UUIDField(null=True, blank=True, verbose_name="ID de warehouse")
    # UUID of billing_company_subscriptions (public schema). No FK: tenant
    # tables cannot reference public tables under django-tenants.
    company_subscription_id = models.UUIDField(
        null=True, blank=True, verbose_name="Período de suscripción",
    )
    request_id = models.CharField(max_length=64, verbose_name="ID de request")
    correlation_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="ID de correlación")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        db_table = 'warehouse_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type'], name='warehouse_e_event_t_idx'),
            models.Index(fields=['warehouse_id'], name='warehouse_e_warehou_idx'),
            models.Index(fields=['created_at'], name='warehouse_e_created_idx'),
            models.Index(fields=['reference_type', 'reference_id'], name='warehouse_e_referen_idx'),
            # Record trace filters by reference_id alone, newest first.
            models.Index(fields=['reference_id', '-created_at'], name='warehouse_e_ref_id_idx'),
            models.Index(fields=['company_subscription_id'], name='warehouse_e_company_idx'),
            # Scope trace: one warehouse, newest first.
            models.Index(fields=['warehouse_id', '-created_at'], name='warehouse_e_wh_created_idx'),
            # Related trace: ``payload @> '{"refs": ["<id>"]}'``.
            GinIndex(fields=['payload'], opclasses=['jsonb_path_ops'], name='warehouse_e_payload_gin'),
            # Recent activity: newest milestones only, stops at LIMIT.
            models.Index(
                fields=['-created_at', '-id'],
                name='warehouse_e_milestone_idx',
                condition=Q(event_type__in=RECENT_ACTIVITY_EVENT_TYPES),
            ),
        ]

    def __str__(self):
        return f'{self.event_type} @ {self.zone or "N/A"}'
