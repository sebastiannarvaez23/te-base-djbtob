from typing import List

from core.cache import invalidate_cache, use_case_cache
from core.errors import NotFoundException, ValidationAppException
from core.errors.codes import AppErrorCode

from platform.features.configuration.landing.landing.domain.catalog import (
    LANDING_SECTION_CATALOG,
    LANDING_SECTION_KEYS,
)
from platform.features.configuration.landing.landing.domain.interfaces import ILandingSectionRepository
from platform.features.configuration.landing.landing.domain.schemas import (
    LandingSectionSchema,
    PublicLandingSectionsSchema,
)
from core.trace import trace_layer


class ListLandingSectionsUseCase:
    def __init__(self, repository: ILandingSectionRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix='landing_sections_list')
    def execute(self, filters: dict | None = None) -> List[LandingSectionSchema]:
        rows = {s.key: s for s in self.repository.list_all()}
        # Always return catalog order; fill missing rows as visible defaults.
        result: List[LandingSectionSchema] = []
        for defn in LANDING_SECTION_CATALOG:
            existing = rows.get(defn['key'])
            if existing:
                result.append(existing)
            else:
                result.append(LandingSectionSchema(
                    key=defn['key'],
                    is_visible=True,
                    sort_order=defn['sort_order'],
                    label_es=defn['label_es'],
                    label_en=defn['label_en'],
                ))
        f = filters or {}
        if 'key' in f:
            key = f['key'].lower()
            result = [r for r in result if key in r.key.lower()]
        if 'is_visible' in f:
            result = [r for r in result if r.is_visible is f['is_visible']]
        return result


class ToggleLandingSectionUseCase:
    def __init__(self, repository: ILandingSectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, key: str, is_visible: bool) -> LandingSectionSchema:
        if key not in LANDING_SECTION_KEYS:
            raise ValidationAppException(
                AppErrorCode.LANDING_SECTION_UNKNOWN,
                override_detail=f"Unknown landing section key '{key}'.",
            )
        result = self.repository.set_visibility(key, is_visible)
        if not result:
            # Auto-create missing catalog row with the requested visibility.
            defn = next(s for s in LANDING_SECTION_CATALOG if s['key'] == key)
            result = self.repository.upsert(
                key, is_visible=is_visible, sort_order=defn['sort_order'],
            )
        if not result:
            raise NotFoundException(AppErrorCode.LANDING_SECTION_NOT_FOUND)
        invalidate_cache('landing_sections_*')
        return result


class GetPublicLandingSectionsUseCase:
    def __init__(self, repository: ILandingSectionRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix='landing_sections_public')
    def execute(self) -> PublicLandingSectionsSchema:
        rows = {s.key: s.is_visible for s in self.repository.list_all()}
        sections = {
            defn['key']: rows.get(defn['key'], True)
            for defn in LANDING_SECTION_CATALOG
        }
        return PublicLandingSectionsSchema(sections=sections)


class EnsureLandingSectionsUseCase:
    """Upsert catalog defaults (management command / ops)."""

    def __init__(self, repository: ILandingSectionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, *, reset_visibility: bool = False) -> int:
        touched = 0
        for defn in LANDING_SECTION_CATALOG:
            existing = self.repository.get_by_key(defn['key'])
            if existing is None:
                self.repository.upsert(
                    defn['key'], is_visible=True, sort_order=defn['sort_order'],
                )
                touched += 1
            elif reset_visibility:
                self.repository.upsert(
                    defn['key'], is_visible=True, sort_order=defn['sort_order'],
                )
                touched += 1
            elif existing.sort_order != defn['sort_order']:
                self.repository.upsert(
                    defn['key'],
                    is_visible=existing.is_visible,
                    sort_order=defn['sort_order'],
                )
                touched += 1
        invalidate_cache('landing_sections_*')
        return touched
