from django.db import models

from core.ids import uuid7


class Module(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    code        = models.CharField(max_length=100, unique=True, verbose_name='Código')
    name        = models.CharField(max_length=200, verbose_name='Nombre')
    description = models.CharField(max_length=500, blank=True, verbose_name='Descripción')
    icon        = models.CharField(max_length=100, verbose_name='Icono')
    route       = models.CharField(max_length=255, verbose_name='Ruta')
    section     = models.ForeignKey(
        'sections.Section',
        on_delete=models.PROTECT,
        related_name='modules',
        verbose_name='Sección',
    )
    order       = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    is_sidebar  = models.BooleanField(default=True, verbose_name='Menú del sidebar')
    offering = models.CharField(
        max_length=20,
        choices=[('plan', 'Plan'), ('complement', 'Complemento')],
        default='plan',
        verbose_name='Contratación',
    )
    billing_mode = models.CharField(
        max_length=20,
        choices=[
            ('included', 'Incluida en el plan'),
            ('renewal', 'Se adiciona a la suscripción'),
            ('one_time', 'Pago de una sola vez'),
        ],
        default='included',
        verbose_name='Forma de cobro',
    )
    catalog_service_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='Servicio de catálogo',
    )
    is_active   = models.BooleanField(default=True, verbose_name='Activo')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'security_modules'
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['section__order', 'order']

    def __str__(self):
        return f'{self.name} ({self.code})'
