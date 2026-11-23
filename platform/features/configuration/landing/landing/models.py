from django.db import models

from core.ids import uuid7


class LandingSection(models.Model):
    """Visibility toggle for a marketing landing page section."""

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    key = models.CharField(
        max_length=32, unique=True, verbose_name='Section key',
        help_text='Machine-readable section id (e.g. hero, pricing, faq).',
    )
    is_visible = models.BooleanField(
        default=True, verbose_name='Visible',
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name='Sort order',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'landing_sections'
        verbose_name = 'Landing section'
        verbose_name_plural = 'Landing sections'
        ordering = ['sort_order', 'key']

    def __str__(self):
        return f'{self.key} (visible={self.is_visible})'
