from django.db import models

from core.ids import uuid7


class RefundRequest(models.Model):
    """Customer refund ticket: payout and plan switch run only after admin approval."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        ACCEPTED = 'accepted', 'Aprobada'
        PROCESSING = 'processing', 'En proceso'
        COMPLETED = 'completed', 'Completada'
        FAILED = 'failed', 'Fallida'
        REJECTED = 'rejected', 'Rechazada'

    class Kind(models.TextChoices):
        FULL = 'full', 'Total'
        DIFFERENCE = 'difference', 'Diferencia'

    OPEN_STATUSES = (Status.PENDING, Status.ACCEPTED, Status.PROCESSING)
    APPROVED_STATUSES = (Status.ACCEPTED, Status.PROCESSING, Status.COMPLETED, Status.FAILED)

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    ticket_number = models.CharField(max_length=24, unique=True)
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.DO_NOTHING,
        related_name='refund_requests',
    )
    schema_name = models.CharField(max_length=63)
    from_subscription_id = models.UUIDField()
    from_subscription_name = models.CharField(max_length=200)
    to_subscription_id = models.UUIDField()
    to_subscription_name = models.CharField(max_length=200)
    period_id = models.UUIDField()
    charge_id = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    payout_due_on = models.DateField()
    charge_refunded_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gateway_refund_id = models.CharField(max_length=255, blank=True, default='')
    failure_message = models.CharField(max_length=512, blank=True, default='')
    rejection_reason = models.CharField(max_length=500, blank=True, default='')
    requested_by_id = models.UUIDField(null=True, blank=True)
    approved_by_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_refund_requests'
        verbose_name = 'Solicitud de reembolso'
        verbose_name_plural = 'Solicitudes de reembolso'
        indexes = [
            models.Index(fields=['company', 'status'], name='refund_company_status_idx'),
            models.Index(fields=['company', '-created_at'], name='refund_company_created_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['company'],
                condition=models.Q(status__in=['pending', 'accepted', 'processing']),
                name='refund_one_open_per_company',
            ),
        ]
