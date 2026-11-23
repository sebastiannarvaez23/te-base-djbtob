"""Política de visibilidad y gobierno del handbook.

Lectura:
- ``public`` publicado → cualquiera.
- ``admin`` sin permiso → cualquier usuario autenticado de plataforma.
  Con permiso → ese permiso, o superuser. Una sesión de operación no alcanza.
- ``wms`` sin permiso → cualquier usuario autenticado de operación, y también
  plataforma. Con permiso → el cliente necesita ese permiso; plataforma ve
  todo el contenido de cliente. Sin sesión no se ve.
- Borradores / working copy → staff (``can_propose`` o ``can_approve``).
- Denegado → no encontrado (no filtrar existencia).

Escritura:
- Proponer: admin tecnológico (``admin.docs.propose``). Nunca un admin de cliente.
- Publicar: solo Administrador de Plataforma (``is_superuser`` o
  ``admin.docs.approve``) vía solicitud aprobada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from core.errors import (
    AppErrorCode,
    AuthException,
    NotFoundException,
    PermissionException,
    ValidationAppException,
)

from handbook.core.constants import (
    APPROVE_FEATURE_KEY,
    AUDIENCE_ADMIN,
    AUDIENCE_PUBLIC,
    AUDIENCE_WMS,
    AUDIENCES,
    KINDS,
    PROPOSE_FEATURE_KEY,
    STATUS_PUBLISHED,
    STATUSES,
)
from handbook.core.viewer import HandbookViewer


@dataclass(frozen=True)
class HandbookAccessTarget:
    """Proyección mínima de una sección/página para evaluar ACL."""

    audience: str
    feature_key: Optional[str] = None
    status: str = STATUS_PUBLISHED


def can_propose(viewer: HandbookViewer) -> bool:
    """Admin tecnológico: redacta working copy y envía la solicitud."""
    if viewer.kind != 'admin':
        return False
    return viewer.has(PROPOSE_FEATURE_KEY)


def can_approve(viewer: HandbookViewer) -> bool:
    """Administrador de Plataforma: aplica o descarta la solicitud."""
    if viewer.kind != 'admin':
        return False
    return viewer.is_superuser or viewer.has(APPROVE_FEATURE_KEY)


def can_manage(viewer: HandbookViewer) -> bool:
    """Staff del CMS (tecnológico o Administrador de Plataforma). No publica."""
    return can_propose(viewer) or can_approve(viewer)


def can_view(target: HandbookAccessTarget, viewer: HandbookViewer) -> bool:
    if target.audience not in AUDIENCES:
        return False
    if target.status not in STATUSES:
        return False

    if target.status != STATUS_PUBLISHED:
        return can_manage(viewer)

    if target.audience == AUDIENCE_PUBLIC:
        return True

    if target.audience == AUDIENCE_ADMIN:
        if viewer.kind != 'admin':
            return False
        if not target.feature_key:
            return True
        return viewer.has(target.feature_key)

    if target.audience == AUDIENCE_WMS:
        if viewer.kind == 'admin':
            return True
        if viewer.kind != 'client':
            return False
        if not target.feature_key:
            return True
        return viewer.has(target.feature_key)

    return False


def filter_visible(
    targets: Sequence[HandbookAccessTarget],
    viewer: HandbookViewer,
) -> List[HandbookAccessTarget]:
    return [item for item in targets if can_view(item, viewer)]


def assert_valid_audience(audience: str) -> str:
    if audience not in AUDIENCES:
        raise ValidationAppException(AppErrorCode.HBK_INVALID_AUDIENCE)
    return audience


def assert_valid_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValidationAppException(AppErrorCode.HBK_INVALID_KIND)
    return kind


def assert_can_view(target: HandbookAccessTarget, viewer: HandbookViewer) -> None:
    if not can_view(target, viewer):
        raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)


def assert_can_manage(viewer: HandbookViewer) -> None:
    if viewer.kind == 'anonymous':
        raise AuthException(AppErrorCode.AUTH_TOKEN_REQUIRED)
    if not can_manage(viewer):
        raise PermissionException(AppErrorCode.HBK_MANAGE_FORBIDDEN)


def assert_can_propose(viewer: HandbookViewer) -> None:
    if viewer.kind == 'anonymous':
        raise AuthException(AppErrorCode.AUTH_TOKEN_REQUIRED)
    if not can_propose(viewer):
        raise PermissionException(AppErrorCode.HBK_PROPOSE_FORBIDDEN)


def assert_can_approve(viewer: HandbookViewer) -> None:
    if viewer.kind == 'anonymous':
        raise AuthException(AppErrorCode.AUTH_TOKEN_REQUIRED)
    if not can_approve(viewer):
        raise PermissionException(AppErrorCode.HBK_APPROVE_FORBIDDEN)


def iter_visible(
    targets: Iterable[HandbookAccessTarget],
    viewer: HandbookViewer,
) -> Iterable[HandbookAccessTarget]:
    for item in targets:
        if can_view(item, viewer):
            yield item
