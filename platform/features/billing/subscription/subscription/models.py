from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.ids import uuid7


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Precio",
        help_text='Monthly list price mirrored from the linked Neurana catalog service.',
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name='Currency (ISO 4217)',
        help_text='ISO 4217 uppercase (e.g. USD, COP). Mirrored from the catalog service.',
    )
    catalog_service_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Servicio de catálogo',
        help_text='Neurana catalog service that owns this plan price.',
    )
    catalog_service_code = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Código del servicio',
    )
    catalog_service_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Nombre del servicio',
    )
    code             = models.CharField(max_length=50, unique=True, verbose_name="Código")
    description      = models.TextField(blank=True, default='', verbose_name="Descripción")
    logo             = models.CharField(max_length=255, blank=True, default='', verbose_name="Logo")
    is_active        = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    class Meta:
        db_table = 'billing_subscriptions'
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"

    def __str__(self):
        return self.name


class BillingSettings(models.Model):
    """Singleton platform billing parameters (annual discount, etc.)."""

    SINGLETON_KEY = 'default'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    singleton_key = models.CharField(
        max_length=16,
        unique=True,
        default=SINGLETON_KEY,
        verbose_name='Clave',
    )
    annual_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        verbose_name='Descuento anual (%)',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'billing_settings'
        verbose_name = 'Configuración de facturación'
        verbose_name_plural = 'Configuración de facturación'

    def __str__(self):
        return f'Descuento anual {self.annual_discount_percent}%'


class CompanySubscription(models.Model):
    """License of use of a catalog plan for one billing cycle.

    Each paid (or gift) cycle writes a new row. Replacing an active row
    (renew / upgrade / scheduled downgrade) **closes** it; ``cancelled``
    is reserved for an explicit customer cancel.
    """

    class Status(models.TextChoices):
        ACTIVE    = 'active',    'Activa'
        CLOSED    = 'closed',    'Cerrada'
        CANCELLED = 'cancelled', 'Cancelada'
        EXPIRED   = 'expired',   'Vencida'
        SUSPENDED = 'suspended', 'Suspendida'

    class BillingInterval(models.TextChoices):
        MONTHLY = 'monthly', 'Mensual'
        YEARLY  = 'yearly',  'Anual'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='subscription_acquisitions',
        verbose_name="Empresa",
    )
    subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        related_name='acquisitions',
        verbose_name="Plan",
    )
    start_date  = models.DateTimeField(verbose_name="Fecha de inicio")
    end_date    = models.DateTimeField(verbose_name="Fecha de vigencia")
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Estado",
    )
    # Set when the company schedules a DOWNGRADE: they keep the current
    # (higher) plan until end_date; a scheduled task then charges this plan
    # and starts a new acquisition with it. NULL = no pending change.
    pending_subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pending_acquisitions',
        verbose_name="Plan pendiente (downgrade)",
    )
    price_paid  = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Precio pagado")
    billing_interval = models.CharField(
        max_length=16,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        verbose_name="Ciclo de cobro",
    )
    # Interval to apply when ``pending_subscription`` materialises. NULL = keep
    # the current ``billing_interval`` (legacy rows and same-cycle downgrades).
    pending_billing_interval = models.CharField(
        max_length=16,
        choices=BillingInterval.choices,
        null=True, blank=True,
        verbose_name="Ciclo de cobro pendiente",
    )
    auto_renew  = models.BooleanField(default=True, verbose_name="Renovación automática")
    notes       = models.TextField(blank=True, verbose_name="Notas")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    updated_at  = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    class Meta:
        db_table              = 'billing_company_subscriptions'
        verbose_name          = "Adquisición de suscripción"
        verbose_name_plural   = "Adquisiciones de suscripción"
        ordering              = ['-start_date']

    def __str__(self):
        return f"{self.company.name} – {self.subscription.name} (vig. {self.end_date.strftime('%d/%m/%Y')})"


class SubscriptionModule(models.Model):
    """Acceso directo de una suscripción a un módulo (aparece en sidebar)."""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='subscription_modules')
    module_code  = models.CharField(max_length=100, verbose_name="Código del módulo")

    class Meta:
        db_table = 'billing_subscription_modules'
        unique_together = ('subscription', 'module_code')
        verbose_name = 'Módulo de suscripción'
        verbose_name_plural = 'Módulos de suscripción'

    def __str__(self):
        return f'{self.subscription.name} – {self.module_code}'


class SubscriptionFunctionality(models.Model):
    """Funcionalidad habilitada dentro de un plan de suscripción."""
    subscription  = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='subscription_functionalities')
    functionality = models.ForeignKey(
        'functionalities.Functionality',
        on_delete=models.CASCADE,
        related_name='subscription_functionalities',
        verbose_name='Funcionalidad',
    )

    class Meta:
        db_table = 'billing_subscription_functionalities'
        unique_together = ('subscription', 'functionality')
        verbose_name = 'Funcionalidad de suscripción'
        verbose_name_plural = 'Funcionalidades de suscripción'

    def __str__(self):
        return f'{self.subscription.name} – {self.functionality.key}'
