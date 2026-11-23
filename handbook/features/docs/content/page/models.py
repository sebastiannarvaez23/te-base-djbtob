"""Página canónica, revisión de configuración y versión localizada inmutable."""

from django.db import models

from core.ids import uuid7
from handbook.core.constants import (
    AUDIENCE_ADMIN,
    AUDIENCE_PUBLIC,
    AUDIENCE_WMS,
    DEFAULT_LOCALE,
    KIND_MANUAL,
)


class HandbookPage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    slug = models.CharField(max_length=80, unique=True)
    published_revision = models.ForeignKey(
        'HandbookRevision',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name='+',
    )
    draft_revision = models.ForeignKey(
        'HandbookRevision',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'handbook_pages'


class HandbookRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    page = models.ForeignKey(
        HandbookPage,
        on_delete=models.DO_NOTHING,
        related_name='revisions',
    )
    parent_page_id = models.UUIDField(null=True, blank=True)
    show_in_sidebar = models.BooleanField(default=True)
    kind = models.CharField(max_length=32, default=KIND_MANUAL)
    audience = models.CharField(max_length=16, default=AUDIENCE_PUBLIC)
    client_feature = models.ForeignKey(
        'functionalities.Functionality',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name='+',
    )
    admin_feature = models.ForeignKey(
        'platform_roles.AdminFeature',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name='+',
    )
    sort_order = models.PositiveIntegerField(default=0)
    icon = models.CharField(max_length=80, blank=True, default='')
    # Nombre en el sidebar de una página sin contenido (agrupa páginas hijas).
    menu_title = models.CharField(max_length=200, blank=True, default='')
    # Solo páginas de tipo API: método HTTP mostrado como etiqueta en el sidebar.
    http_method = models.CharField(max_length=8, blank=True, default='')
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    locales = models.ManyToManyField(
        'HandbookLocaleVersion',
        related_name='revisions',
        blank=True,
    )

    class Meta:
        db_table = 'handbook_revisions'
        constraints = [
            models.CheckConstraint(
                name='handbook_revision_audience_features',
                check=(
                    models.Q(audience=AUDIENCE_PUBLIC, client_feature__isnull=True, admin_feature__isnull=True)
                    | models.Q(audience=AUDIENCE_WMS, admin_feature__isnull=True)
                    | models.Q(audience=AUDIENCE_ADMIN, client_feature__isnull=True)
                ),
            ),
        ]


class HandbookLocaleVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    page = models.ForeignKey(
        HandbookPage,
        on_delete=models.DO_NOTHING,
        related_name='locale_versions',
    )
    locale = models.CharField(max_length=2, default=DEFAULT_LOCALE)
    version = models.CharField(max_length=16)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    search_text = models.TextField(blank=True, default='')
    bucket = models.CharField(max_length=63)
    object_key = models.CharField(max_length=512)
    content_sha256 = models.CharField(max_length=64)
    author_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'handbook_locale_versions'
        constraints = [
            models.UniqueConstraint(
                fields=('page', 'locale', 'version'),
                name='handbook_locale_version_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['object_key'], name='handbook_lv_object_key_idx'),
        ]
