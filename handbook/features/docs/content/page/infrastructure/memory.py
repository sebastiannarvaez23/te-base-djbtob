"""Documento en memoria para tests de reglas (sin PostgreSQL ni MinIO)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from core.ids import uuid7
from handbook.core.constants import CHANGE_REQUEST_PENDING, STATUS_DRAFT, STATUS_PUBLISHED
from handbook.features.docs.content.page.domain.interfaces import IHandbookDocumentStore, IMarkdownStore
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
from handbook.features.docs.content.page.domain.rules import (
    catalog_title,
    feature_display,
    feature_ref,
    is_protected_handbook_root,
)


@dataclass
class _Page:
    id: UUID
    slug: str
    published: dict | None = None
    draft: dict | None = None
    pending: bool = False
    versions: dict[tuple[str, str], str] = field(default_factory=dict)


class MemoryMarkdownStore(IMarkdownStore):
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, object_key: str, body: bytes) -> None:
        self.objects[object_key] = body

    def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    def get(self, object_key: str) -> bytes:
        if object_key not in self.objects:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        return self.objects[object_key]


class MemoryDocumentStore(IHandbookDocumentStore):
    def __init__(self, features: list[FeatureOptionView] | None = None):
        self.pages: dict[UUID, _Page] = {}
        self.features = {item.id: item for item in (features or [])}

    def parent_map(self) -> dict[UUID, UUID | None]:
        result = {}
        for page in self.pages.values():
            config = page.draft or page.published
            if config is None:
                continue
            result[page.id] = config['parent_id']
        return result

    def slug_owner(self, slug: str) -> UUID | None:
        for page in self.pages.values():
            if page.slug == slug:
                return page.id
        return None

    def object_key_owner(self, object_key: str) -> UUID | None:
        for page in self.pages.values():
            for config in (page.draft, page.published):
                if config and any(row.object_key == object_key for row in config['locales']):
                    return page.id
        return None

    def resolve_feature_key(
        self,
        audience: str,
        feature_id: UUID | None,
        *,
        required_category: str | None = None,
    ) -> str | None:
        if feature_id is None:
            return None
        feature = self.features.get(feature_id)
        if feature is None or not feature.audience == audience:
            raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        if required_category and (feature.category or '') != required_category:
            raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        return feature.key

    def list_features(
        self,
        *,
        audience: str,
        query: str,
        offset: int,
        limit: int,
        category: str | None = None,
    ):
        needle = (query or '').lower()
        rows = [
            feature for feature in self.features.values()
            if feature.audience == audience
            and (not category or (feature.category or '') == category)
            and (
                not needle
                or needle in feature.label.lower()
                or needle in feature.key.lower()
                or needle in feature.module.lower()
            )
        ]
        return rows[offset:offset + limit], len(rows)

    def taken_versions(self, page_id: UUID) -> set[tuple[str, str]]:
        page = self.pages.get(page_id)
        if page is None or not page.published:
            return set()
        return {(row.locale, row.version) for row in page.published['locales']}

    def published_locales(self, page_id: UUID) -> list[LocaleVersionView]:
        page = self.pages.get(page_id)
        if page is None or not page.published:
            return []
        return list(page.published['locales'])

    def save_draft(self, page_id, draft: SavePageDraftSchema, *, author_id, stored, carried) -> ManagePageView:
        page = self.pages.get(page_id)
        sort_order = draft.sort_order
        if page is None:
            sort_order = self._place_new_page(draft.parent_id, draft.sort_order)
            page = _Page(id=page_id, slug=draft.slug)
            self.pages[page_id] = page
        page.slug = draft.slug
        revision_id = uuid7()
        locales = stored + carried
        for row in stored:
            page.versions[(row.locale, row.version)] = row.object_key
        page.draft = {
            'revision_id': revision_id,
            'parent_id': draft.parent_id,
            'show_in_sidebar': draft.show_in_sidebar,
            'audience': draft.audience,
            'kind': draft.kind,
            'client_feature_id': draft.client_feature_id,
            'admin_feature_id': draft.admin_feature_id,
            'sort_order': sort_order,
            'icon': draft.icon,
            'menu_title': draft.menu_title,
            'http_method': draft.http_method,
            'locales': locales,
        }
        return self._view(page)

    def _place_new_page(self, parent_id, requested: int) -> int:
        siblings = []
        for page in self.pages.values():
            config = page.draft or page.published
            if not config or config.get('parent_id') != parent_id:
                continue
            siblings.append((config.get('sort_order', 0), page.slug, page))
        siblings.sort(key=lambda item: (item[0], item[1]))
        index = max(0, min(int(requested or 0), len(siblings)))
        for position, (_order, _slug, page) in enumerate(siblings):
            target = position if position < index else position + 1
            seen: list = []
            for config in (page.draft, page.published):
                if not config or config.get('parent_id') != parent_id or config in seen:
                    continue
                seen.append(config)
                config['sort_order'] = target
        return index

    def list_manage(self, *, offset: int, limit: int) -> tuple[list[ManagePageView], int]:
        rows = [self._view(page) for page in self.pages.values()]
        return rows[offset:offset + limit], len(rows)

    def delete_page(self, page_id: UUID) -> list[str]:
        page = self.pages.get(page_id)
        if page is None:
            return []
        if is_protected_handbook_root(
            draft_parent_id=page.draft.get('parent_id') if page.draft else None,
            published_parent_id=page.published.get('parent_id') if page.published else None,
            has_draft=page.draft is not None,
            has_published=page.published is not None,
        ):
            raise ValidationAppException(AppErrorCode.HBK_DELETE_ROOT)
        if any(
            config and config['parent_id'] == page_id
            for other in self.pages.values() if other.id != page_id
            for config in (other.draft, other.published)
        ):
            raise ConflictException(AppErrorCode.HBK_HAS_CHILDREN)
        page = self.pages.pop(page_id)
        keys: list[str] = []
        seen: set[str] = set()
        for key in page.versions.values():
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
        for config in (page.draft, page.published):
            if not config:
                continue
            for row in config.get('locales') or []:
                key = getattr(row, 'object_key', '') or ''
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)
        return keys

    def get_manage(self, page_id: UUID) -> ManagePageView | None:
        page = self.pages.get(page_id)
        if page is None:
            return None
        view = self._view(page)
        feature = self._feature(view.audience, view.client_feature_id, view.admin_feature_id)
        label = feature_display(feature.label, feature.key) if feature else ''
        return view.model_copy(update={'feature_label': label})

    def page_summaries(self, page_ids: Iterable[UUID]) -> dict[UUID, PageSummaryView]:
        summaries = {}
        for page_id in set(page_ids):
            page = self.pages.get(page_id)
            if page is None:
                continue
            config = page.draft or page.published or {}
            locales = [row.locale for row in config.get('locales') or []]
            summaries[page_id] = PageSummaryView(id=page_id, slug=page.slug, locales=locales)
        return summaries

    def list_catalog(self, locale: str) -> list[CatalogNodeView]:
        nodes = []
        for page in self.pages.values():
            config = page.published
            if not config or not config['show_in_sidebar']:
                continue
            titles = {row.locale: row.title for row in config['locales']}
            title, has_content = catalog_title(titles, locale, config.get('menu_title', ''))
            readable, feature_key = self._readable(config)
            if not title or not readable:
                continue
            nodes.append(CatalogNodeView(
                id=page.id,
                parent_id=config['parent_id'],
                slug=page.slug,
                title=title,
                has_content=has_content,
                locale=locale,
                audience=config['audience'],
                feature_key=feature_key,
                kind=config['kind'],
                http_method=config.get('http_method', ''),
                icon=config.get('icon', ''),
                status=STATUS_PUBLISHED,
                sort_order=config['sort_order'],
            ))
        return sorted(nodes, key=lambda item: (item.sort_order, item.title))

    def read_published(self, slug: str, locale: str) -> PublishedPageView | None:
        page = next((item for item in self.pages.values() if item.slug == slug and item.published), None)
        return self._published_view(page, locale) if page else None

    def read_published_by_feature(self, feature_key: str, locale: str) -> PublishedPageView | None:
        needle = (feature_key or '').strip()
        if not needle:
            return None
        matches = [
            page for page in self.pages.values()
            if page.published
            and self._readable(page.published) == (True, needle)
            and any(row.locale == locale for row in page.published['locales'])
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: (item.published['sort_order'], item.slug))
        return self._published_view(matches[0], locale)

    def search(self, locale: str, query: str) -> list[SearchHitView]:
        needle = (query or '').lower()
        hits = []
        for page in self.pages.values():
            if not page.published:
                continue
            match = next((row for row in page.published['locales'] if row.locale == locale), None)
            if match is None:
                continue
            blob = f'{match.title}\n{match.description}\n{match.markdown}'.lower()
            readable, feature_key = self._readable(page.published)
            if needle not in blob or not readable:
                continue
            hits.append(SearchHitView(
                slug=page.slug,
                title=match.title,
                excerpt=match.markdown[:160],
                kind=page.published['kind'],
                audience=page.published['audience'],
                feature_key=feature_key,
            ))
        return hits

    def _published_view(self, page: _Page, locale: str) -> PublishedPageView | None:
        config = page.published
        readable, feature_key = self._readable(config)
        match = next((row for row in config['locales'] if row.locale == locale), None)
        if not readable or match is None:
            return None
        return PublishedPageView(
            id=page.id,
            node_id=page.id,
            slug=page.slug,
            title=match.title,
            description=match.description,
            locale=locale,
            audience=config['audience'],
            feature_key=feature_key,
            status=STATUS_PUBLISHED,
            published_markdown=match.markdown,
            document_version=match.version,
            updated_at=match.created_at,
        )

    def _feature(self, audience: str, client_id: UUID | None, admin_id: UUID | None) -> FeatureOptionView | None:
        feature = self.features.get(feature_ref(audience, client_id, admin_id))
        return feature if feature and feature.audience == audience else None

    def _readable(self, config: dict) -> tuple[bool, str | None]:
        """Igual que el ORM: una funcionalidad ausente (inactiva) oculta la página."""
        if feature_ref(config['audience'], config['client_feature_id'], config['admin_feature_id']) is None:
            return True, None
        feature = self._feature(config['audience'], config['client_feature_id'], config['admin_feature_id'])
        return (True, feature.key) if feature else (False, None)

    def has_pending(self, page_id: UUID) -> bool:
        page = self.pages.get(page_id)
        return bool(page and page.pending)

    def draft_revision_id(self, page_id: UUID) -> UUID | None:
        page = self.pages.get(page_id)
        if page is None or not page.draft:
            return None
        return page.draft['revision_id']

    def published_revision_id(self, page_id: UUID) -> UUID | None:
        page = self.pages.get(page_id)
        if page is None or not page.published:
            return None
        return page.published['revision_id']

    def publish(self, page_id: UUID) -> None:
        page = self.pages[page_id]
        page.published = page.draft
        page.draft = None
        page.pending = False

    def _view(self, page: _Page) -> ManagePageView:
        config = page.draft or page.published or {}
        status = CHANGE_REQUEST_PENDING if page.pending else (
            STATUS_PUBLISHED if page.published and not page.draft else STATUS_DRAFT
        )
        return ManagePageView(
            id=page.id,
            slug=page.slug,
            parent_id=config.get('parent_id'),
            show_in_sidebar=config.get('show_in_sidebar', True),
            audience=config.get('audience', 'public'),
            kind=config.get('kind', 'manual'),
            client_feature_id=config.get('client_feature_id'),
            admin_feature_id=config.get('admin_feature_id'),
            sort_order=config.get('sort_order', 0),
            icon=config.get('icon', ''),
            menu_title=config.get('menu_title', ''),
            http_method=config.get('http_method', ''),
            status=status,
            versions=list(config.get('locales') or []),
            has_pending_request=page.pending,
        )
