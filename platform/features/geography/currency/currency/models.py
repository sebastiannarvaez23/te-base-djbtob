from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.ids import uuid7


_CURRENCY_CODE_RE = r'^[A-Z]{3}$'


class Currency(models.Model):
    """ISO 4217 currency master."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(
        max_length=3,
        unique=True,
        validators=[
            RegexValidator(
                regex=_CURRENCY_CODE_RE,
                message='Currency code must be ISO 4217 alpha-3 (e.g. USD).',
            ),
        ],
        help_text='ISO 4217 uppercase (e.g. USD, COP).',
    )
    name = models.CharField(max_length=120)
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geography_currencies'
        ordering = ['code']
        verbose_name = 'Currency'
        verbose_name_plural = 'Currencies'
        constraints = [
            models.CheckConstraint(
                check=models.Q(code__regex=_CURRENCY_CODE_RE),
                name='chk_geography_currency_iso',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'


class CountryCurrency(models.Model):
    """Allowed currencies for a geography country (N:M with default flag)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    country = models.ForeignKey(
        'geography_location.Country',
        on_delete=models.DO_NOTHING,
        related_name='country_currencies',
        db_constraint=True,
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.DO_NOTHING,
        related_name='country_links',
        db_constraint=True,
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geography_country_currencies'
        ordering = ['country_id', 'currency__code']
        verbose_name = 'Country currency'
        verbose_name_plural = 'Country currencies'
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'currency'],
                name='uq_geography_country_currency',
            ),
            models.UniqueConstraint(
                fields=['country'],
                condition=models.Q(is_default=True),
                name='uq_geography_country_one_default_currency',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.country_id}:{getattr(self.currency, "code", self.currency_id)}'
