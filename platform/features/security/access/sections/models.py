from django.db import models

from core.ids import uuid7


class Section(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    code    = models.CharField(max_length=50, unique=True, verbose_name='Código')
    name    = models.CharField(max_length=200, verbose_name='Nombre')
    icon    = models.CharField(max_length=100, blank=True, default='', verbose_name='Icono')
    order   = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'security_sections'
        ordering = ['order']
        verbose_name = 'Sección'
        verbose_name_plural = 'Secciones'

    def __str__(self):
        return self.name
