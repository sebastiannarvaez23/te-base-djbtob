from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

from core.ids import uuid7


class CompanyLifecycle(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    CLOSED = 'CLOSED', 'Closed'
    PENDING_PURGE = 'PENDING_PURGE', 'Pending purge'
    GONE = 'GONE', 'Gone'


class Company(TenantMixin):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    nit = models.CharField(max_length=40, blank=True, default='')
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    geo_city = models.ForeignKey(
        'geography_location.City',
        on_delete=models.DO_NOTHING,
        related_name='companies',
        db_constraint=True,
    )
    created = models.DateField(auto_now=True)
    lifecycle = models.CharField(
        max_length=16,
        choices=CompanyLifecycle.choices,
        default=CompanyLifecycle.ACTIVE,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=500, blank=True, default='')
    closed_by_admin_id = models.UUIDField(null=True, blank=True)
    legal_hold = models.BooleanField(default=False)
    legal_hold_reason = models.CharField(max_length=500, blank=True, default='')
    export_attested_at = models.DateTimeField(null=True, blank=True)
    export_attested_by = models.UUIDField(null=True, blank=True)
    export_object_key = models.CharField(max_length=500, blank=True, default='')
    users_tombstoned = models.PositiveIntegerField(default=0)

    auto_create_schema = True

    class Meta:
        db_table = 'companies'
        indexes = [
            models.Index(fields=['geo_city'], name='idx_companies_geo_city'),
            models.Index(fields=['lifecycle', 'purge_after'], name='idx_companies_lifecycle_purge'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['nit'],
                condition=~models.Q(nit=''),
                name='uniq_company_nit_when_set',
            ),
        ]

    def __str__(self):
        return self.name


class ClosedTenantRecord(models.Model):
    """Fiscal / identity anchor after the tenant schema is dropped."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    company_id = models.UUIDField(unique=True)
    nit = models.CharField(max_length=40, blank=True, default='')
    name = models.CharField(max_length=200)
    schema_name = models.CharField(max_length=63)
    closed_at = models.DateTimeField()
    purged_at = models.DateTimeField(null=True, blank=True)
    users_tombstoned = models.PositiveIntegerField(default=0)
    schema_dropped = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'closed_tenant_records'


class Domain(DomainMixin):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        db_table = 'domains'
