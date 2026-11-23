"""Adaptador ORM del documento y blobs MinIO."""

from __future__ import annotations

import logging
from typing import Iterable
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q

from core.errors import AppErrorCode, ConflictException, ValidationAppException
from core.ids import uuid7
from core.locks import advisory_xact_lock
from core.storage.domain.schemas import UploadFileSchema
from core.storage.infrastructure.minio_storage import MinioStorageService
from handbook.core.constants import (
    AUDIENCE_ADMIN,
    AUDIENCE_PUBLIC,
    AUDIENCE_WMS,
    CHANGE_REQUEST_PENDING,
    HANDBOOK_BUCKET,
    HANDBOOK_MARKDOWN_CONTENT_TYPE,
    KIND_MANUAL,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
)
from handbook.features.docs.content.page.domain.interfaces import IHandbookDocumentStore, IMarkdownStore
from handbook.features.docs.content.page.domain.rules import (
    catalog_title,
    feature_ref,
    is_protected_handbook_root,
)
from handbook.features.docs.content.page.domain.schemas import (
    CatalogNodeView,
    FeatureOptionView,
    LocaleVersionView,
    ManagePageView,
    PageSummaryView,
    PublishedPageView,
    SavePageDraftSchema,
    SearchHitView,
)
from handbook.features.docs.content.page.infrastructure import features
from handbook.features.docs.content.page.models import (
    HandbookLocaleVersion,
    HandbookPage,
    HandbookRevision,
)
from handbook.features.docs.governance.change_request.models import HandbookChangeRequest

logger = logging.getLogger('app.errors')

SEARCH_TEXT_MAX = 8000
EXCERPT_MAX = 160


class MinioMarkdownStore(IMarkdownStore):
    def __init__(self, storage=None):
        self.storage = storage or MinioStorageService()

    def put(self, object_key: str, body: bytes) -> None:
        self.storage.upload_file(UploadFileSchema(
            bucket=HANDBOOK_BUCKET,
            object_name=object_key,
            data=body,
            content_type=HANDBOOK_MARKDOWN_CONTENT_TYPE,
        ))

    def get(self, object_key: str) -> bytes:
        return self.storage.download_file(HANDBOOK_BUCKET, object_key)

    def delete(self, object_key: str) -> None:
        try:
            self.storage.delete_file(HANDBOOK_BUCKET, object_key)
        except Exception:
            logger.warning('Failed to delete handbook object %s', object_key, exc_info=True)


def _working_pages():
    return HandbookPage.objects.select_related(
        'draft_revision', 'published_revision',
    ).prefetch_related('draft_revision__locales', 'published_revision__locales')


class DjangoHandbookDocumentStore(IHandbookDocumentStore):
    def __init__(self, blobs: IMarkdownStore | None = None):
        self.blobs = blobs or MinioMarkdownStore()

    def parent_map(self) -> dict[UUID, UUID | None]:
        pages = HandbookPage.objects.select_related('draft_revision', 'published_revision')
        result = {}
        for page in pages:
            revision = page.draft_revision or page.published_revision
            if revision is not None:
                result[page.id] = revision.parent_page_id
        return result

    def slug_owner(self, slug: str) -> UUID | None:
        return HandbookPage.objects.filter(slug=slug).values_list('id', flat=True).first()

    def object_key_owner(self, object_key: str) -> UUID | None:
        return HandbookLocaleVersion.objects.filter(
            object_key=object_key,
        ).values_list('page_id', flat=True).first()

    def resolve_feature_key(
        self,
        audience: str,
        feature_id: UUID | None,
        *,
        required_category: str | None = None,
    ) -> str | None:
        if feature_id is None:
            return None
        key = features.active_key(audience, feature_id)
        if not key:
            raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        if required_category:
            category = features.feature_category(audience, feature_id)
            if category != required_category:
                raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        return key

    def list_features(
        self,
        *,
        audience: str,
        query: str,
        offset: int,
        limit: int,
        category: str | None = None,
    ):
        catalog = AUDIENCE_WMS if audience == AUDIENCE_WMS else AUDIENCE_ADMIN
        rows = features.search_features(catalog, query, category=category)
        total = rows.count()
        items = [
            FeatureOptionView(
                id=row.id,
                key=row.key,
                label=row.label,
                module=row.module.name,
                audience=catalog,
                category=getattr(row, 'category', '') or '',
            )
            for row in rows[offset:offset + limit]
        ]
        return items, total

    def taken_versions(self, page_id: UUID) -> set[tuple[str, str]]:
        rows = HandbookLocaleVersion.objects.filter(
            revisions=F('page__published_revision'), page_id=page_id,
        ).values_list('locale', 'version')
        return set(rows)

    def published_locales(self, page_id: UUID) -> list[LocaleVersionView]:
        rows = HandbookLocaleVersion.objects.filter(
            revisions=F('page__published_revision'), page_id=page_id,
        )
        return [self._locale_view(row, include_markdown=False) for row in rows]

    @transaction.atomic
    def save_draft(self, page_id, draft: SavePageDraftSchema, *, author_id, stored, carried) -> ManagePageView:
        # Page and parent locked in pk order: a concurrent delete_page of the parent cannot orphan this draft.
        lock_ids = {page_id} | ({draft.parent_id} if draft.parent_id else set())
        locked = {
            page.id: page
            for page in HandbookPage.objects.select_for_update().filter(pk__in=lock_ids).order_by('pk')
        }
        if draft.parent_id and draft.parent_id != page_id and draft.parent_id not in locked:
            raise ValidationAppException(AppErrorCode.HBK_HIERARCHY_CYCLE)
        page = locked.get(page_id)
        sort_order = draft.sort_order
        if page is None:
            sort_order = self._place_new_page(draft.parent_id, draft.sort_order)
            page = HandbookPage.objects.create(id=page_id, slug=draft.slug)
        else:
            page.slug = draft.slug
            self._drop_draft(page)
        revision = HandbookRevision.objects.create(
            id=uuid7(),
            page=page,
            parent_page_id=draft.parent_id,
            show_in_sidebar=draft.show_in_sidebar,
            kind=draft.kind,
            audience=draft.audience,
            client_feature_id=draft.client_feature_id,
            admin_feature_id=draft.admin_feature_id,
            sort_order=sort_order,
            icon=draft.icon,
            menu_title=draft.menu_title,
            http_method=draft.http_method,
            created_by=author_id,
        )
        HandbookLocaleVersion.objects.bulk_create([
            HandbookLocaleVersion(
                id=row.id,
                page=page,
                locale=row.locale,
                version=row.version,
                title=row.title,
                description=row.description,
                search_text=(row.markdown or '')[:SEARCH_TEXT_MAX],
                bucket=HANDBOOK_BUCKET,
                object_key=row.object_key,
                content_sha256=row.content_sha256,
                author_id=author_id,
            )
            for row in stored
        ])
        revision.locales.set([row.id for row in stored] + [row.id for row in carried])
        page.draft_revision = revision
        page.save(update_fields=['slug', 'draft_revision', 'updated_at'])
        return self.get_manage(page.id)

    def list_manage(self, *, offset: int, limit: int) -> tuple[list[ManagePageView], int]:
        pending_ids = set(HandbookChangeRequest.objects.filter(
            status=CHANGE_REQUEST_PENDING,
        ).values_list('page_id', flat=True))
        pages = _working_pages().order_by('slug')
        total = pages.count()
        return [
            self._manage_view(page, include_markdown=False, pending=page.id in pending_ids)
            for page in pages[offset:offset + limit]
        ], total

    @transaction.atomic
    def delete_page(self, page_id: UUID) -> list[str]:
        page = HandbookPage.objects.select_for_update().filter(pk=page_id).first()
        if page is None:
            return []
        draft = page.draft_revision
        published = page.published_revision
        if is_protected_handbook_root(
            draft_parent_id=draft.parent_page_id if draft is not None else None,
            published_parent_id=published.parent_page_id if published is not None else None,
            has_draft=draft is not None,
            has_published=published is not None,
        ):
            raise ValidationAppException(AppErrorCode.HBK_DELETE_ROOT)
        if self._has_children(page.id):
            raise ConflictException(AppErrorCode.HBK_HAS_CHILDREN)
        keys = list(dict.fromkeys(
            key for key in HandbookLocaleVersion.objects.filter(page_id=page.id).values_list('object_key', flat=True)
            if key
        ))
        HandbookChangeRequest.objects.filter(
            Q(page_id=page.id) | Q(working_revision__page_id=page.id),
        ).delete()
        HandbookPage.objects.filter(pk=page.id).update(draft_revision=None, published_revision=None)
        HandbookRevision.locales.through.objects.filter(handbookrevision__page_id=page.id).delete()
        HandbookLocaleVersion.objects.filter(page_id=page.id).delete()
        HandbookRevision.objects.filter(page_id=page.id).delete()
        HandbookPage.objects.filter(pk=page.id).delete()
        return keys

    @staticmethod
    def _has_children(page_id: UUID) -> bool:
        return HandbookPage.objects.filter(
            Q(draft_revision__parent_page_id=page_id) | Q(published_revision__parent_page_id=page_id),
        ).exclude(pk=page_id).exists()

    def get_manage(self, page_id: UUID) -> ManagePageView | None:
        page = _working_pages().filter(pk=page_id).first()
        if page is None:
            return None
        view = self._manage_view(page, include_markdown=True, pending=self.has_pending(page.id))
        ref = feature_ref(view.audience, view.client_feature_id, view.admin_feature_id)
        return view.model_copy(update={'feature_label': features.feature_label(view.audience, ref)})

    def page_summaries(self, page_ids: Iterable[UUID]) -> dict[UUID, PageSummaryView]:
        ids = set(page_ids)
        if not ids:
            return {}
        summaries = {}
        for page in _working_pages().filter(pk__in=ids):
            revision = page.draft_revision or page.published_revision
            locales = [row.locale for row in revision.locales.all()] if revision else []
            summaries[page.id] = PageSummaryView(id=page.id, slug=page.slug, locales=locales)
        return summaries

    def list_catalog(self, locale: str) -> list[CatalogNodeView]:
        pages = list(
            HandbookPage.objects.filter(published_revision__show_in_sidebar=True)
            .select_related('published_revision').prefetch_related('published_revision__locales'),
        )
        keys = features.active_feature_keys(page.published_revision for page in pages)
        nodes = []
        for page in pages:
            revision = page.published_revision
            titles = {row.locale: row.title for row in revision.locales.all()}
            title, has_content = catalog_title(titles, locale, revision.menu_title)
            readable, feature_key = features.readable_feature(revision, keys)
            if not title or not readable:
                continue
            nodes.append(CatalogNodeView(
                id=page.id,
                parent_id=revision.parent_page_id,
                slug=page.slug,
                title=title,
                locale=locale,
                audience=revision.audience,
                feature_key=feature_key,
                kind=revision.kind,
                http_method=revision.http_method,
                icon=revision.icon,
                status=STATUS_PUBLISHED,
                sort_order=revision.sort_order,
                has_content=has_content,
            ))
        return sorted(nodes, key=lambda item: (item.sort_order, item.title))

    def read_published(self, slug: str, locale: str) -> PublishedPageView | None:
        page = HandbookPage.objects.filter(
            slug=slug, published_revision__isnull=False,
        ).select_related('published_revision').first()
        return self._published_view(page, locale) if page else None

    def read_published_by_feature(self, feature_key: str, locale: str) -> PublishedPageView | None:
        needle = (feature_key or '').strip()
        if not needle:
            return None
        page = (
            HandbookPage.objects.filter(features.bound_to_key(needle), published_revision__locales__locale=locale)
            .select_related('published_revision')
            .order_by('published_revision__sort_order', 'slug')
            .first()
        )
        return self._published_view(page, locale) if page else None

    def _published_view(self, page: HandbookPage, locale: str) -> PublishedPageView | None:
        revision = page.published_revision
        readable, feature_key = features.readable_feature(revision, features.active_feature_keys([revision]))
        if not readable:
            return None
        match = revision.locales.filter(locale=locale).first()
        if match is None:
            return None
        return PublishedPageView(
            id=page.id,
            node_id=page.id,
            slug=page.slug,
            title=match.title,
            description=match.description,
            locale=locale,
            audience=revision.audience,
            feature_key=feature_key,
            status=STATUS_PUBLISHED,
            published_markdown=self.blobs.get(match.object_key).decode('utf-8'),
            document_version=match.version,
            updated_at=match.created_at,
        )

    def search(self, locale: str, query: str) -> list[SearchHitView]:
        needle = (query or '').strip()
        rows = list(HandbookLocaleVersion.objects.filter(
            locale=locale,
            revisions=F('page__published_revision'),
        ).filter(
            Q(title__icontains=needle) | Q(description__icontains=needle) | Q(search_text__icontains=needle),
        ).select_related('page__published_revision'))
        keys = features.active_feature_keys(row.page.published_revision for row in rows)
        hits = []
        for row in rows:
            revision = row.page.published_revision
            readable, feature_key = features.readable_feature(revision, keys)
            if not readable:
                continue
            source = row.search_text or row.description or row.title
            hits.append(SearchHitView(
                slug=row.page.slug,
                title=row.title,
                excerpt=source[:EXCERPT_MAX],
                kind=revision.kind,
                audience=revision.audience,
                feature_key=feature_key,
            ))
        return hits

    def has_pending(self, page_id: UUID) -> bool:
        return HandbookChangeRequest.objects.filter(page_id=page_id, status=CHANGE_REQUEST_PENDING).exists()

    def draft_revision_id(self, page_id: UUID) -> UUID | None:
        return HandbookPage.objects.filter(pk=page_id).values_list('draft_revision_id', flat=True).first()

    def published_revision_id(self, page_id: UUID) -> UUID | None:
        return HandbookPage.objects.filter(pk=page_id).values_list('published_revision_id', flat=True).first()

    def _place_new_page(self, parent_id, requested: int) -> int:
        """Reserva el hueco `requested` entre las hermanas y devuelve ese índice."""
        # Las páginas raíz no tienen fila padre que bloquear: dos altas simultáneas
        # leerían las mismas hermanas y tomarían el mismo índice.
        advisory_xact_lock('handbook_menu', parent_id or 'root')
        siblings = HandbookPage.objects.select_related('draft_revision', 'published_revision').filter(
            Q(draft_revision__isnull=False, draft_revision__parent_page_id=parent_id)
            | Q(draft_revision__isnull=True, published_revision__isnull=False,
                published_revision__parent_page_id=parent_id),
        )
        rows = sorted(
            ((page.draft_revision or page.published_revision).sort_order, page.slug, page)
            for page in siblings
        )
        index = max(0, min(int(requested or 0), len(rows)))
        changed: dict = {}
        for position, (_order, _slug, page) in enumerate(rows):
            target = position if position < index else position + 1
            for revision in (page.draft_revision, page.published_revision):
                if revision is None or revision.parent_page_id != parent_id or revision.sort_order == target:
                    continue
                revision.sort_order = target
                changed[revision.pk] = revision
        if changed:
            HandbookRevision.objects.bulk_update(changed.values(), ['sort_order'])
        return index

    def _drop_draft(self, page: HandbookPage) -> None:
        """Descarta el borrador anterior salvo que esté publicado o en revisión."""
        revision_id = page.draft_revision_id
        if not revision_id or revision_id == page.published_revision_id:
            return
        if HandbookChangeRequest.objects.filter(working_revision_id=revision_id).exists():
            return
        revision = page.draft_revision
        published_ids = set()
        if page.published_revision_id:
            published_ids = set(page.published_revision.locales.values_list('id', flat=True))
        owned_ids = list(revision.locales.exclude(id__in=published_ids).values_list('id', flat=True))
        revision.locales.clear()
        HandbookLocaleVersion.objects.filter(id__in=owned_ids).delete()
        revision.delete()

    def _manage_view(self, page: HandbookPage, *, include_markdown: bool, pending: bool) -> ManagePageView:
        revision = page.draft_revision or page.published_revision
        if pending:
            status = CHANGE_REQUEST_PENDING
        elif page.published_revision_id and page.draft_revision_id is None:
            status = STATUS_PUBLISHED
        else:
            status = STATUS_DRAFT
        versions = []
        if revision is not None:
            versions = [self._locale_view(row, include_markdown=include_markdown) for row in revision.locales.all()]
        return ManagePageView(
            id=page.id,
            slug=page.slug,
            parent_id=getattr(revision, 'parent_page_id', None),
            show_in_sidebar=getattr(revision, 'show_in_sidebar', True),
            audience=getattr(revision, 'audience', AUDIENCE_PUBLIC),
            kind=getattr(revision, 'kind', KIND_MANUAL),
            client_feature_id=getattr(revision, 'client_feature_id', None),
            admin_feature_id=getattr(revision, 'admin_feature_id', None),
            sort_order=getattr(revision, 'sort_order', 0),
            icon=getattr(revision, 'icon', ''),
            menu_title=getattr(revision, 'menu_title', ''),
            http_method=getattr(revision, 'http_method', ''),
            status=status,
            versions=versions,
            has_pending_request=pending,
        )

    def _locale_view(self, row: HandbookLocaleVersion, *, include_markdown: bool) -> LocaleVersionView:
        markdown = ''
        if include_markdown:
            markdown = self.blobs.get(row.object_key).decode('utf-8')
        return LocaleVersionView(
            id=row.id,
            locale=row.locale,
            version=row.version,
            title=row.title,
            description=row.description,
            markdown=markdown,
            object_key=row.object_key,
            content_sha256=row.content_sha256,
            created_at=row.created_at,
        )
