"""Convención de object keys MinIO para el handbook.

El bucket se toma de ``settings.DOCUMENTS_DEFAULT_BUCKET`` (privado,
URLs prefirmadas). PostgreSQL guarda bucket + key, no el cuerpo.
"""

from handbook.core.constants import HANDBOOK_OBJECT_PREFIX


def markdown_object_key(folder, locale, version) -> str:
    """Clave privada: ``handbook/pages/{slug}/{locale}/{version}.md``."""
    return f'{HANDBOOK_OBJECT_PREFIX}pages/{folder}/{locale}/{version}.md'


def page_folder(slug: str, page_id) -> str:
    """Carpeta alterna cuando otra página ya ocupa la carpeta del slug."""
    return f'{slug}--{str(page_id).replace("-", "")[:8]}'


def asset_object_key(page_id, filename: str) -> str:
    safe = (filename or '').replace('\\', '/').split('/')[-1]
    return f'{HANDBOOK_OBJECT_PREFIX}assets/{page_id}/{safe}'
