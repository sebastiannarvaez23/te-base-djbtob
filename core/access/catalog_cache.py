"""
Caché Redis del estado activo de módulos/secciones del catálogo.

Una sola lectura a PostgreSQL por epoch; las invalidaciones
(``SubscriptionCache.bump_catalog_epoch``) fuerzan reload en el
siguiente request.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.core.cache import caches

from core.access.result import AccessResult
from core.access.subscription import SubscriptionCache

logger = logging.getLogger('app.api')

_TTL = 300
_SNAPSHOT_KEY = 'access:catalog:modules_snapshot'

# La ruta del menú no siempre coincide con el prefijo HTTP.
_API_PREFIX_MODULE_CODES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('company-users', ('USERS_ROLES',)),
    ('company-roles', ('USERS_ROLES',)),
    ('company-features', ('USERS_ROLES',)),
    ('integrations', ('INTEGRATIONS',)),
    ('oauth', ('INTEGRATIONS',)),
    ('assistant', ('WA_ASSISTANT',)),
    ('identity', ('SETTINGS',)),
)


def _cache():
    return caches['access']


class CatalogStatusCache:
    """Snapshot global: códigos de módulo → activo / sección."""

    @staticmethod
    def get_snapshot() -> Optional[dict[str, Any]]:
        if SubscriptionCache.get_catalog_epoch() == 0:
            # Sin bumps: aceptar snapshot si existe (arranque fresco).
            return _cache().get(_SNAPSHOT_KEY)
        local = _cache().get(_SNAPSHOT_KEY)
        if not isinstance(local, dict):
            return None
        try:
            if int(local.get('epoch', -1)) != SubscriptionCache.get_catalog_epoch():
                return None
        except (TypeError, ValueError):
            return None
        return local

    @staticmethod
    def set_snapshot(snapshot: dict[str, Any]) -> None:
        snapshot = dict(snapshot)
        snapshot['epoch'] = SubscriptionCache.get_catalog_epoch()
        _cache().set(_SNAPSHOT_KEY, snapshot, timeout=_TTL)

    @staticmethod
    def load_snapshot() -> dict[str, Any]:
        """Carga todos los módulos del catálogo desde PostgreSQL."""
        by_code: dict[str, dict] = {}
        by_id: dict[str, str] = {}
        by_api_prefix: dict[str, str] = {}
        try:
            from platform.features.security.access.modules.models import Module

            for m in (
                Module.objects
                .select_related('section')
                .only(
                    'id', 'code', 'is_active', 'route',
                    'section__code', 'section__is_active',
                )
            ):
                section = getattr(m, 'section', None)
                section_code = getattr(section, 'code', '') or ''
                section_active = bool(getattr(section, 'is_active', True)) if section else True
                code = (m.code or '').strip()
                if not code:
                    continue
                by_code[code] = {
                    'id': str(m.id),
                    'is_active': bool(m.is_active),
                    'section_code': section_code,
                    'section_active': section_active,
                }
                by_id[str(m.id)] = code
                route = (m.route or '').strip()
                if route:
                    prefix = route.lstrip('/').strip('/')
                    if prefix:
                        by_api_prefix[prefix.lower()] = code
        except Exception:
            logger.warning('CatalogStatusCache: failed to load modules', exc_info=True)
            # No cachear el fallo: un snapshot vacío se interpretaría como
            # "módulo desconocido → permitir" durante todo el TTL.
            return {
                'by_code': {},
                'by_id': {},
                'by_api_prefix': {},
                'ok': False,
            }

        snapshot = {
            'by_code': by_code,
            'by_id': by_id,
            'by_api_prefix': by_api_prefix,
            'ok': True,
        }
        CatalogStatusCache.set_snapshot(snapshot)
        return snapshot

    @staticmethod
    def get_or_load() -> dict[str, Any]:
        snap = CatalogStatusCache.get_snapshot()
        if isinstance(snap, dict):
            return snap
        return CatalogStatusCache.load_snapshot()

    @staticmethod
    def check_module_code(module_code: str) -> AccessResult:
        code = (module_code or '').strip()
        if not code:
            return AccessResult.allowed()
        snap = CatalogStatusCache.get_or_load()
        if not isinstance(snap, dict) or snap.get('ok') is False:
            return AccessResult.module_inactive(module_code=code)
        row = snap.get('by_code', {}).get(code)
        if row is None:
            # Case-insensitive fallback
            lower = {k.lower(): k for k in snap.get('by_code', {})}
            canon = lower.get(code.lower())
            row = snap.get('by_code', {}).get(canon) if canon else None
            if row is not None:
                code = canon  # type: ignore[assignment]
        if row is None:
            # Desconocido: no bloquear (catálogo parcial / módulo no sidebar)
            return AccessResult.allowed()
        if not row.get('section_active', True):
            return AccessResult.section_inactive(
                section_code=row.get('section_code') or '',
                module_code=code,
            )
        if not row.get('is_active', True):
            return AccessResult.module_inactive(module_code=code)
        return AccessResult.allowed()

    @staticmethod
    def check_module_id(module_id: str) -> AccessResult:
        mid = (module_id or '').strip().lower()
        if not mid:
            return AccessResult.allowed()
        snap = CatalogStatusCache.get_or_load()
        if not isinstance(snap, dict) or snap.get('ok') is False:
            return AccessResult.module_inactive()
        code = (snap.get('by_id') or {}).get(mid)
        if not code:
            return AccessResult.module_inactive()
        return CatalogStatusCache.check_module_code(code)

    @staticmethod
    def resolve_code_from_api_path(path: str) -> str:
        """Mapea ``/api/v1/warehouse/orders/...`` → código de módulo vía route del catálogo."""
        raw = (path or '').split('?', 1)[0]
        marker = '/api/v1/'
        if marker not in raw:
            return ''
        rest = raw.split(marker, 1)[1].strip('/').lower()
        if not rest:
            return ''
        snap = CatalogStatusCache.get_or_load()
        prefixes = snap.get('by_api_prefix') or {}
        best = ''
        best_len = -1
        for prefix, code in prefixes.items():
            p = (prefix or '').lower().strip('/')
            if not p:
                continue
            if rest == p or rest.startswith(p + '/'):
                if len(p) > best_len:
                    best = code
                    best_len = len(p)
        if best:
            return best

        by_code = snap.get('by_code') or {}
        if not isinstance(by_code, dict) or snap.get('ok') is False:
            return ''
        canonical = {str(key).lower(): key for key in by_code}
        for prefix, codes in _API_PREFIX_MODULE_CODES:
            if rest != prefix and not rest.startswith(prefix + '/'):
                continue
            if len(prefix) <= best_len:
                continue
            for code in codes:
                if code.lower() in canonical:
                    best = canonical[code.lower()]
                    best_len = len(prefix)
                    break
        return best
