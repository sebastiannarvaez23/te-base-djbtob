from __future__ import annotations

import logging
from typing import Optional

from core.cache import invalidate_cache

from platform.features.configuration.ai.capability_control.domain.interfaces import (
    ICapabilityControlRepository,
)
from platform.features.configuration.ai.capability_control.domain.schemas import (
    CapabilityStubSchema,
    default_capabilities,
)
from platform.features.configuration.ai.capability_control.models import (
    CapabilityControlSettings,
)

logger = logging.getLogger('app.ai')


class DjangoCapabilityControlRepository(ICapabilityControlRepository):

    def _row(self) -> Optional[CapabilityControlSettings]:
        return CapabilityControlSettings.objects.filter(
            singleton_key=CapabilityControlSettings.SINGLETON_KEY,
        ).first()

    def get_all(self) -> list[CapabilityStubSchema]:
        row = self._row()
        if row is None or not row.capabilities:
            return default_capabilities()
        items: list[CapabilityStubSchema] = []
        for key, payload in (row.capabilities or {}).items():
            try:
                data = dict(payload or {})
                data['key'] = key
                items.append(CapabilityStubSchema.model_validate(data))
            except Exception as exc:
                logger.warning('capability control row corrupt key=%s: %s', key, exc)
                continue
        return items or default_capabilities()

    def save_all(self, items: list[CapabilityStubSchema]) -> list[CapabilityStubSchema]:
        payload = {
            item.key: item.model_dump(mode='json', exclude={'runtime_health'})
            for item in items
        }
        CapabilityControlSettings.objects.update_or_create(
            singleton_key=CapabilityControlSettings.SINGLETON_KEY,
            defaults={'capabilities': payload},
        )
        invalidate_cache('ai_capability_control*')
        return items

    def get_updated_at(self):
        row = self._row()
        return row.updated_at if row else None
