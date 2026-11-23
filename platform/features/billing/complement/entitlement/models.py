from django.db import models

from core.ids import uuid7


class CompanyComplement(models.Model):
    """License of one complement for one company.

    Revoking closes the row. A later activation writes a new row.
    Marketplace checkout will fill the nullable commercial hooks.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        REVOKED = 'revoked', 'Revoked'
        EXPIRED = 'expired', 'Expired'

    class BillingMode(models.TextChoices):
        RENEWAL = 'renewal', 'Renewal'
        ONE_TIME = 'one_time', 'One-time'

    class Source(models.TextChoices):
        ADMIN_GRANT = 'admin_grant', 'Admin grant'
        MARKETPLACE = 'marketplace', 'Marketplace'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.DO_NOTHING,
        related_name='complement_licenses',
        verbose_name='Empresa',
    )
    functionality = models.ForeignKey(
        'functionalities.Functionality',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='company_complements',
        verbose_name='Funcionalidad',
    )
    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='company_complement_licenses',
        verbose_name='Módulo',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='Estado',
    )
    billing_mode = models.CharField(
        max_length=20,
        choices=BillingMode.choices,
        verbose_name='Modalidad',
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.ADMIN_GRANT,
        verbose_name='Origen',
    )
    starts_at = models.DateTimeField(verbose_name='Inicio')
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name='Fin')
    catalog_service_id = models.UUIDField(null=True, blank=True, verbose_name='Servicio de catálogo')
    invoice = models.ForeignKey(
        'invoice.Invoice',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='complement_licenses',
        verbose_name='Factura',
    )
    price_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio pagado',
    )
    currency = models.CharField(max_length=3, blank=True, default='', verbose_name='Moneda')
    auto_renew = models.BooleanField(default=False, verbose_name='Renovación automática')
    notes = models.TextField(blank=True, default='', verbose_name='Notas')
    granted_by = models.ForeignKey(
        'platform_users.AdminUser',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='granted_complements',
        verbose_name='Otorgado por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'billing_company_complements'
        verbose_name = 'Complemento de empresa'
        verbose_name_plural = 'Complementos de empresa'
        ordering = ['-starts_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(functionality__isnull=False, module__isnull=True)
                    | models.Q(functionality__isnull=True, module__isnull=False)
                ),
                name='cmp_license_one_target',
            ),
            models.UniqueConstraint(
                fields=['company', 'functionality'],
                condition=models.Q(status='active', functionality__isnull=False),
                name='uniq_active_company_complement',
            ),
            models.UniqueConstraint(
                fields=['company', 'module'],
                condition=models.Q(status='active', module__isnull=False),
                name='uniq_active_company_module_complement',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'status'], name='cmp_company_status_idx'),
        ]

    def __str__(self):
        return f'{self.company_id} – {self.functionality_id} ({self.status})'
