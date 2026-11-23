"""Casos de uso del documento: borrador, catálogo publicado y búsqueda."""

from __future__ import annotations

from uuid import UUID

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.ids import uuid7
from core.trace import trace_layer
from handbook.core.access import (
    HandbookAccessTarget,
    assert_can_manage,
    assert_can_propose,
    assert_can_view,
    can_view,
)
from handbook.core.constants import AUDIENCE_ADMIN, AUDIENCE_WMS, KIND_API, STATUS_PUBLISHED
from handbook.core.storage import markdown_object_key, page_folder
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.domain.interfaces import (
    IHandbookDocumentStore,
    IMarkdownStore,
)
from handbook.features.docs.content.page.domain.rules import (
    assert_kind,
    assert_no_cycle,
    copied_locales,
    feature_ids_for_audience,
    hash_markdown,
    http_method_for_kind,
    normalize_locale,
    normalize_semver,
    normalize_slug,
)
from handbook.features.docs.content.page.domain.schemas import (
    CatalogNodeView,
    FeatureOptionView,
    LocaleVersionView,
    ManagePageView,
    PublishedPageView,
    SavePageDraftSchema,
    SearchHitView,
)

SEARCH_MIN_LENGTH = 2
SEARCH_MAX_LENGTH = 80


class SavePageDraftUseCase:
    def __init__(self, documents: IHandbookDocumentStore, blobs: IMarkdownStore):
        self.documents = documents
        self.blobs = blobs

    @trace_layer('application')
    def execute(
        self,
        draft: SavePageDraftSchema,
        viewer: HandbookViewer,
        *,
        page_id: UUID | None = None,
    ) -> ManagePageView:
        assert_can_manage(viewer)
        slug = normalize_slug(draft.slug)
        kind = assert_kind(draft.kind)
        http_method_for_kind(kind, draft.http_method)
        client_id, admin_id = feature_ids_for_audience(
            draft.audience,
            client_feature_id=draft.client_feature_id,
            admin_feature_id=draft.admin_feature_id,
        )
        self.documents.resolve_feature_key(
            draft.audience,
            client_id or admin_id,
            # API pages may only bind OAuth/API-category functionalities.
            required_category=KIND_API if kind == KIND_API else None,
        )
        owner = self.documents.slug_owner(slug)
        if owner is not None and owner != page_id:
            raise ConflictException(AppErrorCode.HBK_SLUG_TAKEN)
        if page_id is not None and self.documents.has_pending(page_id):
            raise ConflictException(AppErrorCode.HBK_PENDING_EXISTS)

        parents = self.documents.parent_map()
        if page_id is None:
            page_id = uuid7()
        if draft.parent_id is not None and draft.parent_id not in parents and draft.parent_id != page_id:
            raise ValidationAppException(AppErrorCode.HBK_HIERARCHY_CYCLE)
        parents[page_id] = draft.parent_id
        assert_no_cycle(page_id, draft.parent_id, parents)

        uploaded: list[str] = []
        author = UUID(str(viewer.user_id)) if viewer.user_id else None
        try:
            return self._store_versions(draft, page_id, slug, kind, client_id, admin_id, author, uploaded)
        except Exception:
            for key in uploaded:
                self.blobs.delete(key)
            raise

    def _store_versions(self, draft, page_id, slug, kind, client_id, admin_id, author, uploaded):
        taken = self.documents.taken_versions(page_id)
        published = self.documents.published_locales(page_id)
        published_by_key = {(row.locale, row.version): row for row in published}
        seen: set[str] = set()
        stored: list[LocaleVersionView] = []
        reused: list[LocaleVersionView] = []
        for item in draft.versions:
            locale = normalize_locale(item.locale)
            if locale in seen:
                raise ValidationAppException(AppErrorCode.HBK_INVALID_LOCALE)
            seen.add(locale)
            version = normalize_semver(item.version)
            title = item.title.strip()
            description = (item.description or '').strip()
            body, digest = hash_markdown(item.markdown)
            if (locale, version) in taken:
                current = published_by_key.get((locale, version))
                if current is None or not _same_content(current, title, description, digest):
                    raise ConflictException(AppErrorCode.HBK_INVALID_VERSION)
                reused.append(current)
                continue
            key, is_new = self._free_object_key(slug, page_id, locale, version, digest)
            if is_new:
                self.blobs.put(key, body)
                uploaded.append(key)
            stored.append(LocaleVersionView(
                id=uuid7(),
                locale=locale,
                version=version,
                title=title,
                description=description,
                markdown=item.markdown,
                object_key=key,
                content_sha256=digest,
            ))

        carry_keys = copied_locales((row.locale for row in published), seen)
        carried = [row for row in published if row.locale in carry_keys] + reused
        menu_title = (draft.menu_title or '').strip()
        if not stored and not carried and not menu_title:
            raise ValidationAppException(AppErrorCode.HBK_MENU_TITLE_REQUIRED)
        icon = '' if draft.parent_id else (draft.icon or '').strip()
        normalized = draft.model_copy(update={
            'slug': slug,
            'kind': kind,
            'http_method': http_method_for_kind(kind, draft.http_method),
            'audience': draft.audience,
            'client_feature_id': client_id,
            'admin_feature_id': admin_id,
            'icon': icon,
            'menu_title': menu_title,
        })
        return self.documents.save_draft(
            page_id,
            normalized,
            author_id=author,
            stored=stored,
            carried=carried,
        )

    def _free_object_key(
        self, slug: str, page_id: UUID, locale: str, version: str, digest: str,
    ) -> tuple[str, bool]:
        """``(key, is_new)``: an upload never overwrites markdown a row still references.

        ``slug`` folder first; another page's folder falls back to ``slug--id``;
        a re-saved draft of the same version gets a content-hash suffix, which is
        reused as is (no upload) when that exact content is already stored.
        """
        key = markdown_object_key(slug, locale, version)
        owner = self.documents.object_key_owner(key)
        if owner is None:
            return key, True
        folder = slug if owner == page_id else page_folder(slug, page_id)
        if folder != slug:
            key = markdown_object_key(folder, locale, version)
            if self.documents.object_key_owner(key) is None:
                return key, True
        key = markdown_object_key(folder, locale, f'{version}+{digest[:12]}')
        return key, self.documents.object_key_owner(key) is None


def _same_content(current: LocaleVersionView, title: str, description: str, digest: str) -> bool:
    """Una versión ya publicada solo se reutiliza si su contenido no cambió."""
    return (
        current.content_sha256 == digest
        and current.title == title
        and current.description == description
    )


class ListManagePagesUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, viewer: HandbookViewer, *, offset: int = 0, limit: int = 20) -> tuple[list[ManagePageView], int]:
        assert_can_manage(viewer)
        return self.documents.list_manage(offset=offset, limit=limit)


class GetManagePageUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, page_id: UUID, viewer: HandbookViewer) -> ManagePageView:
        assert_can_manage(viewer)
        page = self.documents.get_manage(page_id)
        if page is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        return page


class DeleteHandbookChildUseCase:
    """Quita una página que vive dentro de otra, siempre que ya no agrupe páginas."""

    def __init__(self, documents: IHandbookDocumentStore, blobs: IMarkdownStore):
        self.documents = documents
        self.blobs = blobs

    @trace_layer('application')
    def execute(self, page_id: UUID, viewer: HandbookViewer) -> str:
        assert_can_propose(viewer)
        page = self.documents.get_manage(page_id)
        if page is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        if page.parent_id is None:
            raise ValidationAppException(AppErrorCode.HBK_DELETE_ROOT)
        for key in self.documents.delete_page(page_id):
            if key:
                self.blobs.delete(key)
        return page.slug


class ListFeaturesUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(
        self,
        viewer: HandbookViewer,
        *,
        audience: str,
        query: str = '',
        page: int = 0,
        page_size: int = 20,
        category: str | None = None,
    ) -> tuple[list[FeatureOptionView], int]:
        assert_can_manage(viewer)
        if audience not in (AUDIENCE_ADMIN, AUDIENCE_WMS):
            raise ValidationAppException(AppErrorCode.HBK_INVALID_AUDIENCE)
        return self.documents.list_features(
            audience=audience,
            query=(query or '').strip().lower(),
            offset=max(page, 0) * page_size,
            limit=page_size,
            category=(category or '').strip() or None,
        )


class ListCatalogUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, locale: str, viewer: HandbookViewer) -> list[CatalogNodeView]:
        locale = normalize_locale(locale)
        catalog = self.documents.list_catalog(locale)
        visible = []
        for node in catalog:
            target = HandbookAccessTarget(
                audience=node.audience,
                feature_key=node.feature_key,
                status=STATUS_PUBLISHED,
            )
            if can_view(target, viewer):
                visible.append(node)
        return _prune_empty_menus(visible, catalog)


def _open_to_authenticated_session(node: CatalogNodeView) -> bool:
    """Audiencia de cliente o plataforma, sin un permiso concreto."""
    return node.audience in (AUDIENCE_WMS, AUDIENCE_ADMIN) and not node.feature_key


def _prune_empty_menus(
    nodes: list[CatalogNodeView],
    catalog: list[CatalogNodeView],
) -> list[CatalogNodeView]:
    """Oculta un menú público vacío cuando ninguno de sus hijos es visible.

    Un menú sin hijos se queda. Una página de operación o plataforma sin
    permiso concreto también: basta la sesión de ese sistema.
    """
    catalog_parents = {node.parent_id for node in catalog if node.parent_id}
    while True:
        visible_parents = {node.parent_id for node in nodes if node.parent_id}
        kept = [
            node for node in nodes
            if node.has_content
            or node.id not in catalog_parents
            or node.id in visible_parents
            or _open_to_authenticated_session(node)
        ]
        if len(kept) == len(nodes):
            return kept
        nodes = kept


class GetPublishedHelpUseCase:
    """Guía publicada ligada a la funcionalidad del apartado activo."""

    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, feature_key: str, locale: str, viewer: HandbookViewer) -> PublishedPageView:
        key = (feature_key or '').strip()
        if not key:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        requested = normalize_locale(locale)
        page = self.documents.read_published_by_feature(key, requested)
        if page is None:
            fallback = 'en' if requested == 'es' else 'es'
            page = self.documents.read_published_by_feature(key, fallback)
        if page is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        assert_can_view(HandbookAccessTarget(
            audience=page.audience,
            feature_key=page.feature_key,
            status=STATUS_PUBLISHED,
        ), viewer)
        return page


class GetPublishedPageUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, slug: str, locale: str, viewer: HandbookViewer) -> PublishedPageView:
        locale = normalize_locale(locale)
        page = self.documents.read_published(normalize_slug(slug), locale)
        if page is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        assert_can_view(HandbookAccessTarget(
            audience=page.audience,
            feature_key=page.feature_key,
            status=STATUS_PUBLISHED,
        ), viewer)
        return page


class SearchHandbookUseCase:
    def __init__(self, documents: IHandbookDocumentStore):
        self.documents = documents

    @trace_layer('application')
    def execute(self, locale: str, query: str, viewer: HandbookViewer) -> list[SearchHitView]:
        locale = normalize_locale(locale)
        text = (query or '').strip()
        if len(text) < SEARCH_MIN_LENGTH or len(text) > SEARCH_MAX_LENGTH:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        hits = []
        for hit in self.documents.search(locale, text):
            if can_view(HandbookAccessTarget(
                audience=hit.audience,
                feature_key=hit.feature_key,
                status=STATUS_PUBLISHED,
            ), viewer):
                hits.append(hit)
        return hits
