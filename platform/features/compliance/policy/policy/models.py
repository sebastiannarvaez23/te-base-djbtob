from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from core.ids import uuid7
from .domain.enums import PolicyAudience, PolicyCountryStatus, PolicySubjectType

_POLICY_CODE_RE = r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$'
_POLICY_COUNTRY_RE = r'^[A-Z]{2}$'


class Policy(models.Model):
    """Catálogo de políticas administradas desde la plataforma."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(
        max_length=80,
        unique=True,
        validators=[
            RegexValidator(
                regex=_POLICY_CODE_RE,
                message='Policy code must be uppercase kebab-case (e.g. DATA-PROCESSING).',
            ),
        ],
        help_text='Uppercase kebab-case slug (e.g. DATA-PROCESSING). Used in MinIO object keys.',
    )
    name = models.CharField(max_length=200)
    audience = models.CharField(
        max_length=16,
        choices=[(a.value, a.value) for a in PolicyAudience],
        help_text='client → client/policies/; admin → admin/policies/',
    )
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compliance_policies'
        ordering = ['code']
        verbose_name = 'Policy'
        verbose_name_plural = 'Policies'
        constraints = [
            models.CheckConstraint(
                check=models.Q(code__regex=_POLICY_CODE_RE),
                name='chk_compliance_policy_code_upper',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.code} ({self.audience})'


class PolicyCountry(models.Model):
    """
    Versión de una política para un país (ISO 3166-1 alpha-2).

    - ``draft`` (version=0): editable; markdown en ``.../draft.md``.
    - ``approved``: versión materializada (vN.md) aún no vigente.
    - ``published``: vigente / firmable.
    - ``revoked``: supersedida (historial).
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    policy = models.ForeignKey(
        Policy,
        on_delete=models.DO_NOTHING,
        related_name='countries',
        db_constraint=True,
    )
    country = models.CharField(
        max_length=2,
        help_text='ISO 3166-1 alpha-2 uppercase (e.g. CO, US, MX)',
        validators=[
            RegexValidator(
                regex=_POLICY_COUNTRY_RE,
                message='Country must be an ISO 3166-1 alpha-2 code (e.g. CO).',
            ),
        ],
    )
    version = models.PositiveIntegerField(
        default=0,
        help_text='0 for drafts; >=1 for approved/published/revoked versions.',
    )
    status = models.CharField(
        max_length=16,
        choices=[(s.value, s.value) for s in PolicyCountryStatus],
        default=PolicyCountryStatus.DRAFT.value,
    )
    title = models.CharField(max_length=300)
    object_key = models.CharField(max_length=500)
    content_hash = models.CharField(max_length=64, help_text='SHA-256 hex of markdown bytes')
    byte_size = models.PositiveIntegerField(default=0)
    change_summary = models.TextField(
        blank=True,
        default='',
        help_text='Summary of changes vs the previous published version (required on updates).',
    )
    geo_country = models.ForeignKey(
        'geography_location.Country',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='policy_country_versions',
        db_constraint=True,
        help_text='Link to the locations master country (ISO code still stored in country).',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compliance_policy_countries'
        ordering = ['country', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['policy', 'country', 'version'],
                name='uniq_compliance_policy_country_version',
            ),
            models.UniqueConstraint(
                fields=['policy', 'country'],
                condition=Q(status='published'),
                name='uniq_compliance_policy_country_published',
            ),
            models.UniqueConstraint(
                fields=['policy', 'country'],
                condition=Q(status='draft'),
                name='uniq_compliance_policy_country_draft',
            ),
            models.UniqueConstraint(
                fields=['policy', 'country'],
                condition=Q(status='approved'),
                name='uniq_compliance_policy_country_approved',
            ),
            models.CheckConstraint(
                check=models.Q(country__regex=_POLICY_COUNTRY_RE),
                name='chk_compliance_policy_country_iso',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(status='draft', version=0)
                    | models.Q(status__in=['approved', 'published', 'revoked'], version__gte=1)
                ),
                name='chk_compliance_policy_country_version_status',
            ),
        ]
        indexes = [
            models.Index(
                fields=['policy', 'country', 'status'],
                name='idx_pol_country_status',
            ),
        ]
        verbose_name = 'Policy country version'
        verbose_name_plural = 'Policy country versions'

    def __str__(self) -> str:
        return f'{self.policy_id}:{self.country}:v{self.version}({self.status})'


class PolicySignature(models.Model):
    """Firma digital append-only de un sujeto sobre una versión (content_hash) por país."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    policy = models.ForeignKey(
        Policy,
        on_delete=models.DO_NOTHING,
        related_name='signatures',
        db_constraint=True,
    )
    policy_country = models.ForeignKey(
        PolicyCountry,
        on_delete=models.DO_NOTHING,
        related_name='signatures',
        db_constraint=True,
    )
    country = models.CharField(max_length=2)
    content_hash = models.CharField(max_length=64)
    subject_type = models.CharField(
        max_length=16,
        choices=[(s.value, s.value) for s in PolicySubjectType],
    )
    subject_id = models.CharField(max_length=64)
    tenant_id = models.CharField(max_length=64, blank=True, default='')
    signed_at = models.DateTimeField()
    seal = models.CharField(max_length=64)
    seal_algorithm = models.CharField(max_length=32)
    canonical_payload = models.TextField()
    ip_address = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.CharField(max_length=512, blank=True, default='')
    request_id = models.CharField(max_length=64, blank=True, default='')
    channel = models.CharField(max_length=32, default='web')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'compliance_policy_signatures'
        ordering = ['-signed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['subject_type', 'subject_id', 'policy_country', 'content_hash'],
                name='uniq_policy_signature_subject_version',
            ),
        ]
        verbose_name = 'Policy signature'
        verbose_name_plural = 'Policy signatures'
        indexes = [
            models.Index(fields=['subject_type', 'subject_id'], name='idx_pol_sig_subject'),
            models.Index(fields=['policy', 'country'], name='idx_pol_sig_policy_country'),
        ]

    def __str__(self) -> str:
        return f'{self.subject_type}:{self.subject_id}@{self.policy_id}/{self.country}'
