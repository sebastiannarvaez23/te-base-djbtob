from __future__ import annotations

import logging
from typing import Optional

from django.core.cache import caches

from core.ai.model_layer.router import default_routing_table
from core.ai.model_layer.schemas import ModelRoutingTable
from core.cache import invalidate_cache

from platform.features.configuration.ai.model_routing.domain.interfaces import IModelRoutingRepository
from platform.features.configuration.ai.model_routing.models import ModelRoutingSettings

logger = logging.getLogger('app.ai')

_CACHE_KEY = 'ai_model_routing:table'
_CACHE_TTL = 60


def _access_cache():
    try:
        return caches['access']
    except Exception:
        return None


class DjangoModelRoutingRepository(IModelRoutingRepository):

    def _row(self) -> Optional[ModelRoutingSettings]:
        return ModelRoutingSettings.objects.filter(
            singleton_key=ModelRoutingSettings.SINGLETON_KEY,
        ).first()

    def get_table(self) -> ModelRoutingTable:
        row = self._row()
        if row is None or not row.routes:
            return default_routing_table()
        try:
            return ModelRoutingTable.model_validate({
                'routes': row.routes,
                'hourly_budget_usd': row.hourly_budget_usd,
            })
        except Exception as exc:
            logger.warning('model routing table corrupt, using defaults: %s', exc)
            return default_routing_table()

    def save_table(self, table: ModelRoutingTable) -> ModelRoutingTable:
        payload = {
            cap: route.model_dump(mode='json')
            for cap, route in table.routes.items()
        }
        row, _ = ModelRoutingSettings.objects.update_or_create(
            singleton_key=ModelRoutingSettings.SINGLETON_KEY,
            defaults={
                'routes': payload,
                'hourly_budget_usd': table.hourly_budget_usd,
            },
        )
        invalidate_cache('ai_model_routing*')
        return ModelRoutingTable.model_validate({
            'routes': row.routes,
            'hourly_budget_usd': row.hourly_budget_usd,
        })

    def get_updated_at(self):
        row = self._row()
        return row.updated_at if row else None


def load_routing_table() -> ModelRoutingTable:
    """Helper for chat / harness — Redis TTL cache to avoid PG on every turn."""
    cache = _access_cache()
    if cache is not None:
        try:
            cached = cache.get(_CACHE_KEY)
            if isinstance(cached, ModelRoutingTable):
                return cached
            if isinstance(cached, dict):
                return ModelRoutingTable.model_validate(cached)
        except Exception as exc:
            logger.debug('routing table cache read failed: %s', exc)
    try:
        table = DjangoModelRoutingRepository().get_table()
    except Exception:
        return default_routing_table()
    if cache is not None:
        try:
            cache.set(_CACHE_KEY, table.model_dump(mode='json'), timeout=_CACHE_TTL)
        except Exception as exc:
            logger.debug('routing table cache write failed: %s', exc)
    return table
