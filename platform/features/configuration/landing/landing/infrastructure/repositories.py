from typing import List, Optional

from platform.features.configuration.landing.landing.domain.catalog import LANDING_SECTION_CATALOG
from platform.features.configuration.landing.landing.domain.interfaces import ILandingSectionRepository
from platform.features.configuration.landing.landing.domain.schemas import LandingSectionSchema
from platform.features.configuration.landing.landing.models import LandingSection

_LABELS = {s['key']: s for s in LANDING_SECTION_CATALOG}


def _to_schema(obj: LandingSection) -> LandingSectionSchema:
    meta = _LABELS.get(obj.key, {})
    return LandingSectionSchema(
        id=obj.id,
        key=obj.key,
        is_visible=obj.is_visible,
        sort_order=obj.sort_order,
        label_es=meta.get('label_es', obj.key),
        label_en=meta.get('label_en', obj.key),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoLandingSectionRepository(ILandingSectionRepository):

    def list_all(self) -> List[LandingSectionSchema]:
        return [_to_schema(obj) for obj in LandingSection.objects.order_by('sort_order', 'key')]

    def get_by_key(self, key: str) -> Optional[LandingSectionSchema]:
        try:
            return _to_schema(LandingSection.objects.get(key=key))
        except LandingSection.DoesNotExist:
            return None

    def upsert(
        self, key: str, *, is_visible: bool, sort_order: int,
    ) -> LandingSectionSchema:
        obj, _ = LandingSection.objects.update_or_create(
            key=key,
            defaults={'is_visible': is_visible, 'sort_order': sort_order},
        )
        return _to_schema(obj)

    def set_visibility(self, key: str, is_visible: bool) -> Optional[LandingSectionSchema]:
        try:
            obj = LandingSection.objects.get(key=key)
        except LandingSection.DoesNotExist:
            return None
        obj.is_visible = is_visible
        obj.save(update_fields=['is_visible', 'updated_at'])
        return _to_schema(obj)
