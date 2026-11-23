"""
core/access/entity_scope.py
───────────────────────────
Alcance por entidad: qué registros puede ver un usuario.

Regla: sin accesos otorgados el usuario no ve nada; el rol Administrator
ve todo. Los accesos viven en el schema del tenant
(``client/features/security/access/entity_grants``); aquí solo se resuelven
y cachean. El feature dueño registra el loader en ``AppConfig.ready()``.

Costo por request: memo en el request → Redis (``caches['access']``, un solo
``get_many`` con valor y versión) → una consulta por índice único
(index-only scan) si la caché expiró, quedó vieja o falló.

Consistencia: cada valor guarda la versión leída antes de consultar la base.
Un cambio de accesos asigna versión nueva al confirmar, así que un valor
escrito por una lectura concurrente con datos previos nunca vuelve a servirse.

Uso en una vista, cuando el producto haya registrado un tipo:
    scope = resolve_entity_scope(request, entity_type)
    use_case.list(..., allowed_ids=scope.ids_or_none)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from uuid import UUID

from django.core.cache import caches
from django.db import connection

from core.access.billing_recovery import is_company_admin
from core.access.entity_types import EntityScopeType
from core.cache.invalidation import bump_versions, new_version

logger = logging.getLogger('app.api')

_TTL = 300
_VERSION_TTL = 86_400  # mayor que _TTL: la versión sobrevive a sus valores y se recrea poco
_PREFIX = 'egrant'
_MEMO_ATTR = '_wa_entity_scopes'


__all__ = [
    'DENIED',
    'UNRESTRICTED',
    'EntityScope',
    'EntityScopeType',
    'grant_entity_access',
    'invalidate_entity_scope',
    'register_grant_loader',
    'register_grant_writer',
    'resolve_entity_scope',
]

GrantLoader = Callable[[UUID, EntityScopeType], set[UUID]]
GrantWriter = Callable[[UUID, EntityScopeType, UUID, Optional[UUID]], None]
_loader: Optional[GrantLoader] = None
_writer: Optional[GrantWriter] = None


@dataclass(frozen=True)
class EntityScope:
    """``unrestricted`` ignora ``ids`` (administrador)."""

    unrestricted: bool
    ids: frozenset[UUID] = frozenset()

    def allows(self, entity_id: UUID) -> bool:
        return self.unrestricted or entity_id in self.ids

    @property
    def ids_or_none(self) -> Optional[frozenset[UUID]]:
        """``None`` = sin restricción; conjunto (quizá vacío) = filtrar por esos IDs."""
        return None if self.unrestricted else self.ids


UNRESTRICTED = EntityScope(unrestricted=True)
DENIED = EntityScope(unrestricted=False)


def register_grant_loader(loader: GrantLoader) -> None:
    global _loader
    _loader = loader


def register_grant_writer(writer: GrantWriter) -> None:
    global _writer
    _writer = writer


def grant_entity_access(
    user_id: UUID, entity_type: EntityScopeType, entity_id: UUID, granted_by: Optional[UUID] = None,
) -> None:
    """Otorga un acceso (idempotente). Sin writer registrado falla: quien llama hace rollback."""
    if _writer is None:
        raise RuntimeError('Entity grant writer not registered')
    _writer(user_id, entity_type, entity_id, granted_by)


def _key(user_id: UUID, entity_type: EntityScopeType) -> str:
    schema = getattr(connection, 'schema_name', None) or 'public'
    return f'{_PREFIX}:{schema}:{user_id}:{entity_type.value}'


def _version_key(user_id: UUID, entity_type: EntityScopeType) -> str:
    return f'{_key(user_id, entity_type)}:v'


def _current_version(cache, version_key: str, found: Optional[str]) -> str:
    """Versión vigente; si no existe (primera vez o expulsada), la crea sin pisar otra."""
    if found is not None:
        return found
    created = new_version()
    if cache.add(version_key, created, timeout=_VERSION_TTL):
        return created
    return cache.get(version_key) or created


def _load(user_id: UUID, entity_type: EntityScopeType) -> frozenset[UUID]:
    cache = caches['access']
    key, version_key = _key(user_id, entity_type), _version_key(user_id, entity_type)
    found = cache.get_many([key, version_key])
    entry = found.get(key)
    version = found.get(version_key)
    if version is not None and isinstance(entry, dict) and entry.get('v') == version:
        return frozenset(UUID(item) for item in entry['ids'])
    if _loader is None:
        logger.error('Entity grant loader not registered; denying entity_type=%s', entity_type.value)
        return frozenset()
    version = _current_version(cache, version_key, version)
    ids = frozenset(_loader(user_id, entity_type))
    cache.set(key, {'v': version, 'ids': [str(item) for item in ids]}, timeout=_TTL)
    return ids


def resolve_entity_scope(request, entity_type: EntityScopeType) -> EntityScope:
    """Alcance del usuario autenticado para ``entity_type`` (memo por request)."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return DENIED
    if is_company_admin(user):
        return UNRESTRICTED
    memo: dict[EntityScopeType, EntityScope] = getattr(request, _MEMO_ATTR, None) or {}
    if entity_type not in memo:
        memo[entity_type] = EntityScope(unrestricted=False, ids=_load(user.id, entity_type))
        setattr(request, _MEMO_ATTR, memo)
    return memo[entity_type]


def invalidate_entity_scope(user_ids: Iterable[UUID], entity_type: EntityScopeType) -> None:
    bump_versions((_version_key(user_id, entity_type) for user_id in user_ids), timeout=_VERSION_TTL)
