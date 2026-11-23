from django.db import models
from django.utils import timezone

from core.ids import uuid7


class FiscalOutboxEvent(models.Model):
    """Pending fiscal command for Neurana, written in the same transaction as
    the base invoice change (transactional outbox) and drained by the relay."""

    class Kind(models.TextChoices):
        ISSUE = 'issue', 'Issue'
        VOID = 'void', 'Void'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        DONE = 'done', 'Done'
        DEAD = 'dead', 'Dead'

    class DeadReason(models.TextChoices):
        NONE = '', 'None'
        REJECTED = 'rejected', 'Rejected'
        EXPIRED = 'expired', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    invoice_id = models.UUIDField(db_index=True)
    charge_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True)
    reason = models.CharField(max_length=200, blank=True, default='')
    trace_id = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    last_error_code = models.CharField(max_length=40, blank=True, default='')
    dead_reason = models.CharField(
        max_length=12, choices=DeadReason.choices, blank=True, default='',
    )
    alerted_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'fiscal_outbox'
        db_table = 'billing_fiscal_outbox_events'
        verbose_name = 'Fiscal outbox event'
        verbose_name_plural = 'Fiscal outbox events'
        indexes = [
            models.Index(fields=['status', 'next_attempt_at'], name='fiscal_outbox_due_idx'),
            models.Index(fields=['invoice_id', 'kind'], name='fiscal_outbox_invoice_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.kind}:{self.invoice_id}:{self.status}'
