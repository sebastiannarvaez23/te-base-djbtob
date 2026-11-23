from django.db import models

from core.ids import uuid7


class Charge(models.Model):
    """
    Orden de cobro propia del dominio.

    Es la fuente de verdad del ciclo de vida de un pago en base.
    El estado interno manda; el provider solo *sugiere* transiciones que
    valida la state machine de :mod:`...domain.state_machine`.
    """

    class Status(models.TextChoices):
        PENDING            = 'pending',             'Pendiente'
        PROCESSING         = 'processing',          'Procesando'
        REQUIRES_ACTION    = 'requires_action',     'Requiere acción del usuario'
        AUTHORIZED         = 'authorized',          'Autorizado'
        CAPTURED           = 'captured',            'Capturado'
        FAILED             = 'failed',              'Fallido'
        CANCELED           = 'canceled',            'Cancelado'
        REFUNDED           = 'refunded',            'Reembolsado'
        PARTIALLY_REFUNDED = 'partially_refunded',  'Reembolsado parcialmente'
        DISPUTED           = 'disputed',            'En disputa'

    class MethodType(models.TextChoices):
        CARD           = 'card',           'Tarjeta'
        BANK_TRANSFER  = 'bank_transfer',  'Transferencia bancaria'
        PSE            = 'pse',            'PSE'
        WALLET         = 'wallet',         'Billetera digital'
        VOUCHER        = 'voucher',        'Recaudo en efectivo'
        BNPL           = 'bnpl',           'Pago a cuotas'
        CRYPTO         = 'crypto',         'Criptomoneda'
        OTHER          = 'other',          'Otro'

    class NextActionType(models.TextChoices):
        REDIRECT        = 'redirect',        'Redirección'
        DISPLAY_QR      = 'display_qr',      'Mostrar QR'
        DISPLAY_VOUCHER = 'display_voucher', 'Mostrar comprobante'
        AWAIT_WEBHOOK   = 'await_webhook',   'Esperar webhook'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")

    # Identificadores externos / idempotencia
    idempotency_key = models.CharField(
        max_length=128, unique=True, null=True, blank=True,
        verbose_name="Clave de idempotencia",
    )
    gateway_provider = models.CharField(
        max_length=50, verbose_name="Proveedor de pago",
        help_text="Identificador del adapter usado (simulator, stripe, wompi, ...).",
    )
    gateway_charge_id = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Id del cargo en el proveedor",
    )

    # Relaciones
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.SET_NULL,
        related_name='charges',
        verbose_name="Empresa",
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        'invoice.Invoice',
        on_delete=models.DO_NOTHING,
        related_name='charges',
        null=True, blank=True,
        verbose_name="Factura asociada",
    )
    payment_method = models.ForeignKey(
        'payment_method.PaymentMethod',
        on_delete=models.DO_NOTHING,
        related_name='charges',
        null=True, blank=True,
        verbose_name="Método de pago",
    )
    company_subscription = models.ForeignKey(
        'subscription.CompanySubscription',
        on_delete=models.DO_NOTHING,
        related_name='period_charges',
        null=True,
        blank=True,
        verbose_name="Período de suscripción",
    )

    # Datos del cargo
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Monto")
    currency = models.CharField(max_length=3, default='COP', verbose_name="Moneda (ISO 4217)")
    method_type = models.CharField(
        max_length=20, choices=MethodType.choices, default=MethodType.CARD,
        verbose_name="Tipo de método",
    )
    description = models.CharField(max_length=255, blank=True, default='', verbose_name="Descripción")
    tenant_nit = models.CharField(max_length=40, blank=True, default='', verbose_name="NIT al cobrar")
    tenant_name = models.CharField(max_length=200, blank=True, default='', verbose_name="Razón social al cobrar")

    # Estado y next-action
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
        verbose_name="Estado",
    )
    next_action_type = models.CharField(
        max_length=20, choices=NextActionType.choices, blank=True, default='',
        verbose_name="Tipo de acción siguiente",
    )
    next_action_url = models.URLField(blank=True, default='', verbose_name="URL de acción siguiente")

    # Fallos
    failure_code = models.CharField(max_length=64, blank=True, default='', verbose_name="Código de fallo")
    failure_message = models.CharField(max_length=255, blank=True, default='', verbose_name="Mensaje de fallo")

    # Marcas temporales del ciclo
    authorized_at = models.DateTimeField(null=True, blank=True, verbose_name="Autorizado en")
    captured_at = models.DateTimeField(null=True, blank=True, verbose_name="Capturado en")
    canceled_at = models.DateTimeField(null=True, blank=True, verbose_name="Cancelado en")
    refunded_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Monto reembolsado",
    )

    # Datos libres
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadatos")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    class Meta:
        db_table = 'billing_charges'
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at'], name='idx_charge_company_created'),
            models.Index(fields=['gateway_provider', 'gateway_charge_id'], name='idx_charge_gateway_ref'),
            models.Index(fields=['status'], name='idx_charge_status'),
        ]

    def __str__(self):
        return f"{self.gateway_provider}:{self.gateway_charge_id or self.id} ({self.status})"


class ChargeAttempt(models.Model):
    """
    Cada llamada al gateway por un Charge.

    Sirve como bitácora técnica (debug, soporte) y como base de
    reintentos. No reemplaza al WebhookInbox: aquí van las respuestas
    síncronas; allá las asíncronas.
    """

    class Operation(models.TextChoices):
        CREATE   = 'create',   'Crear cargo'
        CONFIRM  = 'confirm',  'Confirmar'
        CAPTURE  = 'capture',  'Capturar'
        CANCEL   = 'cancel',   'Cancelar'
        REFUND   = 'refund',   'Reembolsar'
        FETCH    = 'fetch',    'Consultar'

    class Result(models.TextChoices):
        SUCCEEDED = 'succeeded', 'Exitoso'
        FAILED    = 'failed',    'Fallido'
        PENDING   = 'pending',   'Pendiente'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    charge = models.ForeignKey(
        Charge,
        on_delete=models.DO_NOTHING,
        related_name='attempts',
        verbose_name="Cargo",
    )
    operation = models.CharField(max_length=20, choices=Operation.choices, verbose_name="Operación")
    gateway_provider = models.CharField(max_length=50, verbose_name="Proveedor")
    request_payload = models.JSONField(default=dict, blank=True, verbose_name="Payload de salida")
    response_payload = models.JSONField(default=dict, blank=True, verbose_name="Payload de respuesta")
    result = models.CharField(max_length=20, choices=Result.choices, verbose_name="Resultado")
    error_message = models.CharField(max_length=512, blank=True, default='', verbose_name="Error")
    attempted_at = models.DateTimeField(auto_now_add=True, verbose_name="Intentado en")

    class Meta:
        db_table = 'billing_charge_attempts'
        verbose_name = "Intento de cargo"
        verbose_name_plural = "Intentos de cargo"
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['charge', '-attempted_at'], name='idx_attempt_charge_time'),
        ]

    def __str__(self):
        return f"{self.charge_id} · {self.operation} → {self.result}"


class WebhookInbox(models.Model):
    """
    Inbox pattern para webhooks entrantes.

    El endpoint guarda el payload crudo *antes* de procesarlo y responde
    200 inmediatamente. Un worker (FASE 2/3) lee filas con
    ``processed_at IS NULL`` y aplica el WebhookTranslator del provider.
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    provider = models.CharField(max_length=50, verbose_name="Proveedor")
    external_event_id = models.CharField(max_length=255, verbose_name="Id externo del evento")
    event_type = models.CharField(max_length=100, blank=True, default='', verbose_name="Tipo de evento")
    payload = models.JSONField(default=dict, verbose_name="Payload")
    signature = models.CharField(max_length=512, blank=True, default='', verbose_name="Firma")
    signature_verified = models.BooleanField(default=False, verbose_name="Firma verificada")
    received_at = models.DateTimeField(auto_now_add=True, verbose_name="Recibido en")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Procesado en")
    processing_error = models.CharField(max_length=512, blank=True, default='', verbose_name="Error de procesamiento")
    charge = models.ForeignKey(
        Charge,
        on_delete=models.DO_NOTHING,
        related_name='webhook_events',
        null=True, blank=True,
        verbose_name="Cargo relacionado",
    )

    class Meta:
        db_table = 'billing_webhook_inbox'
        verbose_name = "Webhook entrante"
        verbose_name_plural = "Webhooks entrantes"
        ordering = ['-received_at']
        unique_together = ('provider', 'external_event_id')
        indexes = [
            models.Index(fields=['processed_at'], name='idx_inbox_processed_at'),
            models.Index(fields=['provider', '-received_at'], name='idx_inbox_provider_time'),
        ]

    def __str__(self):
        return f"{self.provider}:{self.external_event_id}"


class IdempotencyKey(models.Model):
    """
    Caché de respuestas para garantizar safe-retry en operaciones
    salientes al provider (create_charge, refund, etc.).

    Si llega un segundo create_charge con la misma key y mismo
    request_hash, devolvemos la respuesta cacheada. Si la key es la
    misma pero el body cambió, la capa que consuma rechazará el intento.
    """

    key = models.CharField(max_length=128, primary_key=True, verbose_name="Clave")
    scope = models.CharField(max_length=100, verbose_name="Operación protegida")
    request_hash = models.CharField(max_length=64, verbose_name="Hash del request (sha256)")
    response_payload = models.JSONField(default=dict, blank=True, verbose_name="Respuesta cacheada")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    expires_at = models.DateTimeField(verbose_name="Expira en")

    class Meta:
        db_table = 'billing_idempotency_keys'
        verbose_name = "Clave de idempotencia"
        verbose_name_plural = "Claves de idempotencia"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['scope', '-created_at'], name='idx_idem_scope_time'),
            models.Index(fields=['expires_at'], name='idx_idem_expires_at'),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key}"
