"""Convenciones de almacenamiento MinIO para políticas (.md).

Bucket: ``base`` (PROFILE_BUCKET).
Object keys (privados; no se añaden a la policy pública del bucket)::

    client/policies/{CODE}/{COUNTRY}/v{n}.md
    admin/policies/{CODE}/{COUNTRY}/v{n}.md
    client/policies/{CODE}/{COUNTRY}/draft.md   # mutable draft
    admin/policies/{CODE}/{COUNTRY}/draft.md

Cada versión publicada es inmutable: al liberar contenido nuevo se crea otra clave
(vN+1) y la anterior se revoca en metadata (el objeto MinIO se conserva).
"""

from __future__ import annotations

from core.storage.profile_bucket import PROFILE_BUCKET

from .enums import PolicyAudience

POLICY_BUCKET = PROFILE_BUCKET  # 'base'
POLICY_MARKDOWN_CONTENT_TYPE = 'text/markdown; charset=utf-8'
POLICY_OBJECT_PREFIX = {
    PolicyAudience.CLIENT: 'client/policies',
    PolicyAudience.ADMIN: 'admin/policies',
}


def _prefix(audience: PolicyAudience | str, code: str, country: str) -> str:
    aud = PolicyAudience(audience) if not isinstance(audience, PolicyAudience) else audience
    return (
        f'{POLICY_OBJECT_PREFIX[aud]}/{code.strip().upper()}/'
        f'{country.strip().upper()}'
    )


def policy_object_key(
    audience: PolicyAudience | str,
    code: str,
    country: str,
    version: int,
) -> str:
    """Ruta inmutable del markdown de una versión dentro del bucket base."""
    if version < 1:
        raise ValueError('version must be >= 1')
    return f'{_prefix(audience, code, country)}/v{int(version)}.md'


def policy_draft_object_key(
    audience: PolicyAudience | str,
    code: str,
    country: str,
) -> str:
    """Ruta mutable del borrador por país."""
    return f'{_prefix(audience, code, country)}/draft.md'


def policy_prefix(audience: PolicyAudience | str, code: str) -> str:
    """Prefijo de todos los países/versiones de una política (para listar/borrar)."""
    aud = PolicyAudience(audience) if not isinstance(audience, PolicyAudience) else audience
    prefix = POLICY_OBJECT_PREFIX[aud]
    return f'{prefix}/{code.strip().upper()}/'
