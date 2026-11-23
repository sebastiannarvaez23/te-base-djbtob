from django.db import models

from core.ids import uuid7


class Functionality(models.Model):
    class Offering(models.TextChoices):
        PLAN = 'plan', 'Plan'
        COMPLEMENT = 'complement', 'Complemento'

    class BillingMode(models.TextChoices):
        INCLUDED = 'included', 'Incluida en el plan'
        RENEWAL = 'renewal', 'Renovación'
        ONE_TIME = 'one_time', 'Adquisición única'

    id        = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    key       = models.CharField(max_length=100, unique=True, verbose_name='Clave')
    label     = models.CharField(max_length=200, verbose_name='Etiqueta')
    module    = models.ForeignKey(
        'modules.Module',
        on_delete=models.PROTECT,
        related_name='functionalities',
        verbose_name='Módulo',
    )
    category  = models.CharField(max_length=50, default='features', verbose_name='Categoría')
    offering = models.CharField(
        max_length=20,
        choices=Offering.choices,
        default=Offering.PLAN,
        verbose_name='Contratación',
    )
    billing_mode = models.CharField(
        max_length=20,
        choices=BillingMode.choices,
        default=BillingMode.INCLUDED,
        verbose_name='Modalidad',
    )
    catalog_service_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='Servicio de catálogo',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'security_features'
        verbose_name = 'Funcionalidad'
        verbose_name_plural = 'Funcionalidades'
        ordering = ['module__order', 'key']

    def __str__(self):
        return f'{self.label} ({self.key})'
