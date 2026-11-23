from django.db import models

from core.ids import uuid7


class DocumentTemplate(models.Model):
    """Reusable multi-format document template.

    Carries all configuration needed for each format it supports
    (HTML, PDF, XLSX, CSV, XML). The 'synchronization' invariant is:
    for every format in `allowed_formats` there must exist a matching
    config in `format_configs` and a backend renderer registered.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    code = models.CharField(
        max_length=80, unique=True, verbose_name='Unique code',
        help_text='Machine-readable identifier (e.g. INVOICE_DEFAULT, REMISSION_V2).',
    )
    name = models.CharField(
        max_length=200, verbose_name='Template name',
        help_text='Human-readable label shown in the admin UI.',
    )
    kind = models.CharField(
        max_length=50, verbose_name='Document kind',
        help_text='Free-form document type tag (e.g. INVOICE, REMISSION, QUOTATION, PURCHASE_ORDER).',
        db_index=True,
    )
    html_template = models.TextField(
        verbose_name='HTML template',
        help_text='Jinja2/Django-style HTML template. Used by HTML and PDF formats.',
    )
    mock_data = models.JSONField(
        verbose_name='Mock data',
        blank=True, default=dict,
        help_text='JSON with sample values for template variables, used for preview emulation.',
    )
    description = models.TextField(
        verbose_name='Description',
        blank=True, default='',
        help_text='Internal notes about when and how this template is used.',
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Active',
    )

    # ── Formats supported ─────────────────────────────────────
    allowed_formats = models.JSONField(
        verbose_name='Allowed formats',
        blank=True, default=list,
        help_text='List of DocumentFormat values, e.g. ["HTML","PDF","XLSX"].',
    )
    default_format = models.CharField(
        max_length=10, default='PDF', verbose_name='Default format',
        help_text='Format used when caller does not specify one. Must be in allowed_formats.',
    )

    # ── Per-format configuration (synchronized with allowed_formats) ──
    format_configs = models.JSONField(
        verbose_name='Per-format configurations',
        blank=True, default=dict,
        help_text=(
            'Object keyed by DocumentFormat. For each format in allowed_formats '
            'a matching config must exist (see domain.format_configs schemas).'
        ),
    )

    # ── Storage ───────────────────────────────────────────────
    is_storable = models.BooleanField(
        default=False, verbose_name='Storable',
        help_text='If true, generated documents are uploaded to MinIO.',
    )
    storage_bucket = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Storage bucket',
        help_text='Override MinIO bucket. Empty → default documents bucket from settings.',
    )
    storage_path_template = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Storage path template',
        help_text=(
            'Interpolated path. Must include {{ uuid }} or {{ timestamp }} for uniqueness. '
            'System vars: {{ uuid }}, {{ timestamp }}, {{ year }}, {{ month }}, {{ day }}, {{ ext }}.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'documents_document_templates'
        verbose_name = 'Document template'
        verbose_name_plural = 'Document templates'
        ordering = ['kind', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'
