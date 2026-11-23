from django.db import models

from core.ids import uuid7


class Invoice(models.Model):

    class InvoiceStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PAID = 'paid', 'Pagada'
        CANCELLED = 'cancelled', 'Cancelada'
        OVERDUE = 'overdue', 'Vencida'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name="Número de factura")
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.SET_NULL,
        related_name='invoices',
        verbose_name="Empresa",
        null=True,
        blank=True,
    )
    subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        related_name='invoices',
        verbose_name="Suscripción",
    )
    company_subscription = models.ForeignKey(
        'subscription.CompanySubscription',
        on_delete=models.DO_NOTHING,
        related_name='period_invoices',
        null=True,
        blank=True,
        verbose_name="Período de suscripción",
    )
    source_charge_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Cobro origen",
    )
    issue_date = models.DateField(verbose_name="Fecha de emisión")
    due_date = models.DateField(verbose_name="Fecha de vencimiento")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto total")
    currency = models.CharField(max_length=3, default='USD', verbose_name="Moneda")
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PENDING,
        verbose_name="Estado",
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    # Snapshot from the charge (promotion serial/amounts, email overlay, …)
    # so PDF resend/download keep the same breakdown without charge metadata.
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadata")
    tenant_nit = models.CharField(max_length=40, blank=True, default='', verbose_name="NIT al emitir")
    tenant_name = models.CharField(max_length=200, blank=True, default='', verbose_name="Razón social al emitir")

    # Set when the invoice PDF is generated and uploaded to MinIO.
    # Empty until SendInvoiceUseCase runs successfully.
    pdf_bucket     = models.CharField(max_length=120, blank=True, default='', verbose_name="Bucket del PDF")
    pdf_object_key = models.CharField(max_length=500, blank=True, default='', verbose_name="Object key del PDF")
    pdf_sent_at    = models.DateTimeField(null=True, blank=True, verbose_name="Enviado al cliente en")

    # Neurana fiscal mirror (Phase 4). Charge never blocks if remote is down.
    class FiscalStatus(models.TextChoices):
        NONE = '', 'None'
        PENDING = 'pending', 'Pending'
        ISSUED = 'issued', 'Issued'
        VOIDING = 'voiding', 'Voiding'
        REJECTED = 'rejected', 'Rejected'
        VOIDED = 'voided', 'Voided'

    external_id = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Fiscal external id',
    )
    fiscal_number = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Fiscal number',
    )
    fiscal_status = models.CharField(
        max_length=20, blank=True, default='', db_index=True,
        verbose_name='Fiscal status',
    )
    fiscal_payload = models.JSONField(default=dict, blank=True, verbose_name='Fiscal payload')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    class Meta:
        db_table = 'billing_invoices'
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-issue_date']

    def __str__(self):
        return self.invoice_number


class NeuranaWebhookInbox(models.Model):
    """Durable inbox for Neurana → base fiscal webhooks (idempotent by event id)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    external_event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=100, blank=True, default='')
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=512, blank=True, default='')
    signature_verified = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.CharField(max_length=512, blank=True, default='')
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.DO_NOTHING,
        related_name='neurana_webhook_events',
        null=True,
        blank=True,
        db_constraint=False,
    )

    class Meta:
        db_table = 'billing_neurana_webhook_inbox'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['processed_at'], name='idx_ne_inbox_processed'),
        ]

    def __str__(self):
        return self.external_event_id

