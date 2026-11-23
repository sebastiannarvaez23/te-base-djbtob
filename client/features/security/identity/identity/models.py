from django.db import models
from django.conf import settings

from core.ids import uuid7


class LanguageChoices(models.TextChoices):
    SPANISH = 'es', 'Español'
    ENGLISH = 'en', 'English'
    PORTUGUESE = 'pt', 'Português'
    FRENCH = 'fr', 'Français'


class ThemeChoices(models.TextChoices):
    LIGHT = 'light', 'Claro'
    DARK = 'dark', 'Oscuro'
    SYSTEM = 'system', 'Sistema'


class DateFormatChoices(models.TextChoices):
    DMY = 'DD/MM/YYYY', 'DD/MM/YYYY'
    MDY = 'MM/DD/YYYY', 'MM/DD/YYYY'
    YMD = 'YYYY-MM-DD', 'YYYY-MM-DD'


class TimeFormatChoices(models.TextChoices):
    H24 = '24', '24'
    H12 = '12', '12'


class UserPreferences(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
        verbose_name='Usuario',
    )
    language = models.CharField(
        max_length=5,
        choices=LanguageChoices.choices,
        default=LanguageChoices.SPANISH,
        verbose_name='Idioma',
    )
    theme = models.CharField(
        max_length=10,
        choices=ThemeChoices.choices,
        default=ThemeChoices.LIGHT,
        verbose_name='Tema',
    )
    timezone = models.CharField(
        max_length=60,
        default='America/Bogota',
        verbose_name='Zona horaria',
    )
    date_format = models.CharField(
        max_length=12,
        choices=DateFormatChoices.choices,
        default=DateFormatChoices.DMY,
        verbose_name='Formato de fecha',
    )
    time_format = models.CharField(
        max_length=2,
        choices=TimeFormatChoices.choices,
        default=TimeFormatChoices.H24,
        verbose_name='Formato de hora',
    )
    sidebar_collapsed = models.BooleanField(
        default=False,
        verbose_name='Barra lateral contraída',
    )
    items_per_page = models.PositiveSmallIntegerField(
        default=20,
        verbose_name='Elementos por página',
    )
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name='Notificaciones activas',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'security_preferences'
        verbose_name = 'Preferencias de usuario'
        verbose_name_plural = 'Preferencias de usuarios'

    def __str__(self):
        return f'Preferencias de {self.user}'
