from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.ids import uuid7


_COUNTRY_CODE_RE = r'^[A-Z]{2}$'
_LOCATION_CODE_RE = r'^[A-Z0-9][A-Z0-9\-_]{0,19}$'


class Country(models.Model):
    """Maestra de países (ISO 3166-1 alpha-2)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(
        max_length=2,
        unique=True,
        validators=[
            RegexValidator(
                regex=_COUNTRY_CODE_RE,
                message='Country code must be ISO 3166-1 alpha-2 (e.g. CO).',
            ),
        ],
        help_text='ISO 3166-1 alpha-2 uppercase (e.g. CO, MX, US).',
    )
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text='Reference latitude for zone access validation.',
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text='Reference longitude for zone access validation.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geography_countries'
        ordering = ['name']
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'
        constraints = [
            models.CheckConstraint(
                check=models.Q(code__regex=_COUNTRY_CODE_RE),
                name='chk_geography_country_iso',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'


class Department(models.Model):
    """Departamento / estado / provincia de un país."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    country = models.ForeignKey(
        Country,
        on_delete=models.DO_NOTHING,
        related_name='departments',
        db_constraint=True,
    )
    code = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=_LOCATION_CODE_RE,
                message='Department code must be alphanumeric (e.g. ANT, 05).',
            ),
        ],
    )
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geography_departments'
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'code'],
                name='uniq_geography_department_country_code',
            ),
        ]
        indexes = [
            models.Index(fields=['country', 'is_active'], name='idx_geo_dept_country_active'),
        ]

    def __str__(self) -> str:
        return f'{self.country_id}:{self.code} — {self.name}'


class City(models.Model):
    """Ciudad / municipio de un departamento."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    department = models.ForeignKey(
        Department,
        on_delete=models.DO_NOTHING,
        related_name='cities',
        db_constraint=True,
    )
    code = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=_LOCATION_CODE_RE,
                message='City code must be alphanumeric (e.g. MED, 05001).',
            ),
        ],
    )
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geography_cities'
        ordering = ['name']
        verbose_name = 'City'
        verbose_name_plural = 'Cities'
        constraints = [
            models.UniqueConstraint(
                fields=['department', 'code'],
                name='uniq_geography_city_department_code',
            ),
        ]
        indexes = [
            models.Index(fields=['department', 'is_active'], name='idx_geo_city_dept_active'),
        ]

    def __str__(self) -> str:
        return f'{self.department_id}:{self.code} — {self.name}'
