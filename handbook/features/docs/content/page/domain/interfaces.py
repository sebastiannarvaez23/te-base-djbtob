from abc import ABC, abstractmethod
from typing import Iterable, Optional
from uuid import UUID

from .schemas import (
    CatalogNodeView,
    FeatureOptionView,
    HandbookPageSchema,
    HandbookVersionSchema,
    LocaleVersionView,
    ManagePageView,
    PageSummaryView,
    PublishedPageView,
    SavePageDraftSchema,
    SearchHitView,
)


class IPageRepository(ABC):
    """Cuerpo markdown versionado (puntero MinIO)."""

    @abstractmethod
    def get_published(self, slug: str, *, locale: str) -> Optional[HandbookPageSchema]:
        ...

    @abstractmethod
    def get_version(self, page_id, version_id) -> Optional[HandbookVersionSchema]:
        ...


class IMarkdownStore(ABC):
    @abstractmethod
    def put(self, object_key: str, body: bytes) -> None:
        ...

    @abstractmethod
    def get(self, object_key: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, object_key: str) -> None:
        """Compensación best-effort de un objeto recién subido: nunca lanza."""


class IHandbookDocumentStore(ABC):
    @abstractmethod
    def parent_map(self) -> dict[UUID, UUID | None]:
        ...

    @abstractmethod
    def slug_owner(self, slug: str) -> UUID | None:
        ...

    @abstractmethod
    def object_key_owner(self, object_key: str) -> UUID | None:
        """Página dueña de un objeto markdown ya registrado."""

    @abstractmethod
    def resolve_feature_key(
        self,
        audience: str,
        feature_id: UUID | None,
        *,
        required_category: str | None = None,
    ) -> str | None:
        ...

    @abstractmethod
    def list_features(
        self,
        *,
        audience: str,
        query: str,
        offset: int,
        limit: int,
        category: str | None = None,
    ) -> tuple[list[FeatureOptionView], int]:
        ...

    @abstractmethod
    def taken_versions(self, page_id: UUID) -> set[tuple[str, str]]:
        """Pares ``(locale, version)`` ya publicados: inmutables."""

    @abstractmethod
    def published_locales(self, page_id: UUID) -> list[LocaleVersionView]:
        ...

    @abstractmethod
    def save_draft(
        self,
        page_id: UUID | None,
        draft: SavePageDraftSchema,
        *,
        author_id: UUID | None,
        stored: list[LocaleVersionView],
        carried: list[LocaleVersionView],
    ) -> ManagePageView:
        ...

    @abstractmethod
    def list_manage(self, *, offset: int, limit: int) -> tuple[list[ManagePageView], int]:
        ...

    @abstractmethod
    def get_manage(self, page_id: UUID) -> ManagePageView | None:
        ...

    @abstractmethod
    def delete_page(self, page_id: UUID) -> list[str]:
        """Borra la página y devuelve las claves de markdown para compensar en el blob store.

        Atómico: si alguna página (borrador o publicada) aún cuelga de ella, lanza HBK_HAS_CHILDREN.
        """
        ...

    @abstractmethod
    def page_summaries(self, page_ids: Iterable[UUID]) -> dict[UUID, PageSummaryView]:
        """Slug e idiomas de la versión de trabajo de cada página, en lote."""

    @abstractmethod
    def list_catalog(self, locale: str) -> list[CatalogNodeView]:
        ...

    @abstractmethod
    def read_published(self, slug: str, locale: str) -> PublishedPageView | None:
        ...

    @abstractmethod
    def read_published_by_feature(self, feature_key: str, locale: str) -> PublishedPageView | None:
        ...

    @abstractmethod
    def search(self, locale: str, query: str) -> list[SearchHitView]:
        ...

    @abstractmethod
    def has_pending(self, page_id: UUID) -> bool:
        ...

    @abstractmethod
    def draft_revision_id(self, page_id: UUID) -> UUID | None:
        ...

    @abstractmethod
    def published_revision_id(self, page_id: UUID) -> UUID | None:
        ...
