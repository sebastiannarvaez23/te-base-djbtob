from django.db import models
from django.db.models import TextChoices

from core.ids import uuid7


class LanguageChoices(TextChoices):
    SPANISH = 'es', 'Español'
    ENGLISH = 'en', 'English'
    PORTUGUESE = 'pt', 'Português'
    FRENCH = 'fr', 'Français'


class ThemeChoices(TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'
    SYSTEM = 'system', 'System'


class DateFormatChoices(TextChoices):
    DMY = 'DD/MM/YYYY', 'DD/MM/YYYY'
    MDY = 'MM/DD/YYYY', 'MM/DD/YYYY'
    YMD = 'YYYY-MM-DD', 'YYYY-MM-DD'


class TimeFormatChoices(TextChoices):
    H24 = '24', '24'
    H12 = '12', '12'


class AdminUserPreferences(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.OneToOneField(
        'platform_users.AdminUser',
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    language = models.CharField(
        max_length=5, choices=LanguageChoices.choices, default=LanguageChoices.SPANISH,
    )
    theme = models.CharField(
        max_length=10, choices=ThemeChoices.choices, default=ThemeChoices.LIGHT,
    )
    timezone = models.CharField(max_length=60, default='America/Bogota')
    date_format = models.CharField(
        max_length=12, choices=DateFormatChoices.choices, default=DateFormatChoices.DMY,
    )
    time_format = models.CharField(
        max_length=2, choices=TimeFormatChoices.choices, default=TimeFormatChoices.H24,
    )
    sidebar_collapsed = models.BooleanField(default=False)
    items_per_page = models.PositiveSmallIntegerField(default=20)
    notifications_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_preferences'
        verbose_name = 'Admin User Preferences'
        verbose_name_plural = 'Admin User Preferences'

    def __str__(self):
        return f'Preferences({self.user_id})'
