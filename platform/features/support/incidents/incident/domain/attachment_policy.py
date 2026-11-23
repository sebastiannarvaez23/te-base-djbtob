"""
Política de evidencia adjunta a incidencias (imágenes, GIF y MP4).

Espejo server-side de ``feedback-media.util.ts`` (wa-components-web): el
cliente valida para UX, aquí se valida porque el cliente no es confiable.
Puro: sin I/O, sin Django.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

MAX_ATTACHMENTS = 5
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_NAME_LENGTH = 255

_BLOCKED_EXTENSIONS = frozenset({
    'exe', 'dll', 'bat', 'cmd', 'com', 'msi', 'scr', 'ps1', 'sh', 'bash',
    'js', 'jsx', 'mjs', 'cjs', 'ts', 'tsx', 'html', 'htm', 'svg', 'xml',
    'php', 'asp', 'aspx', 'jsp', 'cgi', 'py', 'rb', 'pl',
    'jar', 'apk', 'ipa', 'dmg', 'iso', 'vbs', 'vbe', 'wsf', 'wsh',
    'hta', 'cpl', 'msc', 'reg', 'lnk', 'url', 'docm', 'xlsm',
})


@dataclass(frozen=True)
class _Rule:
    mimes: tuple[str, ...]
    kind: str
    max_bytes: int
    canonical_mime: str


_RULES: dict[str, _Rule] = {
    'jpg': _Rule(('image/jpeg',), 'image', MAX_IMAGE_BYTES, 'image/jpeg'),
    'jpeg': _Rule(('image/jpeg',), 'image', MAX_IMAGE_BYTES, 'image/jpeg'),
    'png': _Rule(('image/png',), 'image', MAX_IMAGE_BYTES, 'image/png'),
    'webp': _Rule(('image/webp',), 'image', MAX_IMAGE_BYTES, 'image/webp'),
    'gif': _Rule(('image/gif',), 'gif', MAX_IMAGE_BYTES, 'image/gif'),
    'mp4': _Rule(('video/mp4', 'application/mp4'), 'video', MAX_VIDEO_BYTES, 'video/mp4'),
}

_UNSAFE_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')


@dataclass(frozen=True)
class AcceptedMedia:
    kind: str
    extension: str
    content_type: str
    safe_name: str


def _base_name(filename: str) -> str:
    return re.split(r'[/\\]', (filename or '').strip())[-1]


def _matches_magic(head: bytes, ext: str) -> bool:
    if ext in ('jpg', 'jpeg'):
        return head.startswith(b'\xff\xd8\xff')
    if ext == 'png':
        return head.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == 'gif':
        return head.startswith(b'GIF8')
    if ext == 'webp':
        return head.startswith(b'RIFF') and head[8:12] == b'WEBP'
    if ext == 'mp4':
        return len(head) >= 8 and head[4:8] == b'ftyp'
    return False


def sanitize_name(filename: str) -> str:
    cleaned = _UNSAFE_NAME_CHARS.sub('_', _base_name(filename)).strip(' .')
    return (cleaned or 'evidence')[:MAX_NAME_LENGTH]


def classify_media(filename: str, content_type: str, data: bytes) -> Optional[AcceptedMedia]:
    """Devuelve el medio aceptado o ``None`` si viola la política."""
    if not data:
        return None
    base = _base_name(filename).lower()
    parts = [p for p in base.split('.') if p]
    exts = parts[1:] if len(parts) > 1 else []
    if not exts or any(ext in _BLOCKED_EXTENSIONS for ext in exts):
        return None

    ext = exts[-1]
    rule = _RULES.get(ext)
    if rule is None or len(data) > rule.max_bytes:
        return None

    mime = (content_type or '').split(';', 1)[0].strip().lower()
    if mime and mime != 'application/octet-stream' and mime not in rule.mimes:
        return None
    if not _matches_magic(data[:64], ext):
        return None

    return AcceptedMedia(
        kind=rule.kind,
        extension=ext,
        content_type=rule.canonical_mime,
        safe_name=sanitize_name(filename),
    )
