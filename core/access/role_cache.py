"""
core/access/role_cache.py
─────────────────────────
Caché Redis de feature keys concedidas por rol (tenant).

Usada por HasSubscriptionAccess / AccessChecker para denegar en caliente
cuando el rol pierde features o se desactiva, sin N+1 a RolFeature.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.core.cache import caches

logger = logging.getLogger('app.api')

_TTL = 300
_PREFIX = 'role'


def _cache():
    return caches['access']


class RoleFeatureCache:
    """Caché de keys de funcionalidad habilitadas para un rol tenant."""

    @staticmethod
    def _features_key(role_id: str) -> str:
        return f'{_PREFIX}:{role_id}:features'

    @staticmethod
    def get_features(role_id: str) -> Optional[set[str]]:
        return _cache().get(RoleFeatureCache._features_key(str(role_id)))

    @staticmethod
    def set_features(role_id: str, features: set[str]) -> None:
        _cache().set(RoleFeatureCache._features_key(str(role_id)), features, timeout=_TTL)

    @staticmethod
    def invalidate(role_id: str) -> None:
        _cache().delete(RoleFeatureCache._features_key(str(role_id)))

    @staticmethod
    def load_features(role_id: str) -> set[str]:
        """Carga desde DB las features activas del rol (módulo y feature activos)."""
        try:
            from client.features.security.lifecycle.registration.models import RolFeature

            keys = set(
                RolFeature.objects.filter(
                    rol_id=role_id,
                    feature__is_active=True,
                    feature__module__is_active=True,
                    feature__module__section__is_active=True,
                ).values_list('feature__key', flat=True)
            )
            RoleFeatureCache.set_features(role_id, keys)
            return keys
        except Exception:
            logger.warning('Failed to load role features role_id=%s', role_id, exc_info=True)
            return set()

    @staticmethod
    def get_or_load(role_id: str) -> set[str]:
        cached = RoleFeatureCache.get_features(role_id)
        if cached is not None:
            return cached
        return RoleFeatureCache.load_features(role_id)
