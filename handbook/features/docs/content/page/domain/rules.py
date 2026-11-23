"""Reglas puras de slug, semver, jerarquía y audiencia."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, Mapping
from uuid import UUID

from core.errors import AppErrorCode, ValidationAppException
from handbook.core.access import assert_valid_audience, assert_valid_kind
from handbook.core.constants import (
    AUDIENCE_ADMIN,
    AUDIENCE_PUBLIC,
    AUDIENCE_WMS,
    HANDBOOK_MARKDOWN_MAX_BYTES,
    HTTP_METHODS,
    KIND_API,
    LOCALES,
)

SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
SEMVER_PATTERN = re.compile(r'^\d+\.\d+(?:\.\d+)?$')


def normalize_slug(slug: str) -> str:
    text = (slug or '').strip().lower()
    if not SLUG_PATTERN.fullmatch(text) or len(text) > 80:
        raise ValidationAppException(AppErrorCode.HBK_INVALID_SLUG)
    return text


def normalize_locale(locale: str) -> str:
    text = (locale or '').strip().lower()
    if text not in LOCALES:
        raise ValidationAppException(AppErrorCode.HBK_INVALID_LOCALE)
    return text


def normalize_semver(version: str) -> str:
    text = (version or '').strip()
    if not SEMVER_PATTERN.fullmatch(text):
        raise ValidationAppException(AppErrorCode.HBK_INVALID_VERSION)
    return text


def assert_no_cycle(page_id: UUID, parent_id: UUID | None, parents: Mapping[UUID, UUID | None]) -> None:
    if parent_id is None:
        return
    if parent_id == page_id or parent_id not in parents:
        raise ValidationAppException(AppErrorCode.HBK_HIERARCHY_CYCLE)
    seen = {page_id}
    cursor: UUID | None = parent_id
    while cursor is not None:
        if cursor in seen:
            raise ValidationAppException(AppErrorCode.HBK_HIERARCHY_CYCLE)
        seen.add(cursor)
        cursor = parents.get(cursor)
        if cursor is not None and cursor not in parents and cursor not in seen:
            raise ValidationAppException(AppErrorCode.HBK_HIERARCHY_CYCLE)


def feature_ids_for_audience(
    audience: str,
    *,
    client_feature_id: UUID | None,
    admin_feature_id: UUID | None,
) -> tuple[UUID | None, UUID | None]:
    audience = assert_valid_audience(audience)
    if audience == AUDIENCE_PUBLIC:
        if client_feature_id or admin_feature_id:
            raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        return None, None
    if audience == AUDIENCE_WMS:
        if admin_feature_id:
            raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
        return client_feature_id, None
    if client_feature_id:
        raise ValidationAppException(AppErrorCode.HBK_FEATURE_INVALID)
    return None, admin_feature_id


def assert_kind(kind: str) -> str:
    return assert_valid_kind(kind)


def http_method_for_kind(kind: str, method: str | None) -> str:
    """Una página API exige su método HTTP; los demás tipos no llevan método."""
    if kind != KIND_API:
        return ''
    text = (method or '').strip().upper()
    if text not in HTTP_METHODS:
        raise ValidationAppException(AppErrorCode.HBK_HTTP_METHOD_REQUIRED)
    return text


def hash_markdown(raw: str) -> tuple[bytes, str]:
    text = raw if raw is not None else ''
    if not text.strip():
        raise ValidationAppException(AppErrorCode.HBK_MARKDOWN_INVALID)
    try:
        body = text.encode('utf-8')
    except UnicodeError as exc:
        raise ValidationAppException(AppErrorCode.HBK_MARKDOWN_INVALID) from exc
    if len(body) > HANDBOOK_MARKDOWN_MAX_BYTES:
        raise ValidationAppException(AppErrorCode.HBK_MARKDOWN_INVALID)
    return body, hashlib.sha256(body).hexdigest()


def copied_locales(existing: Iterable[str], incoming: Iterable[str]) -> set[str]:
    return set(existing) - set(incoming)


def feature_ref(audience: str, client_feature_id: UUID | None, admin_feature_id: UUID | None) -> UUID | None:
    """Funcionalidad que gobierna el acceso según la audiencia de la revisión."""
    if audience == AUDIENCE_WMS:
        return client_feature_id
    if audience == AUDIENCE_ADMIN:
        return admin_feature_id
    return None


def catalog_title(titles: Mapping[str, str], locale: str, menu_title: str) -> tuple[str, bool]:
    """Título del nodo en ``locale`` y si tiene contenido propio.

    Una página sin ningún idioma es un menú (``menu_title``); una con
    contenido solo en otro idioma no aparece en este.
    """
    if locale in titles:
        return titles[locale], True
    return ('' if titles else (menu_title or '').strip()), False


def feature_display(label: str, key: str) -> str:
    return f'{label} · {key}'


def is_protected_handbook_root(
    *,
    draft_parent_id: UUID | None,
    published_parent_id: UUID | None,
    has_draft: bool,
    has_published: bool,
) -> bool:
    """Top-level pages stay, including a published root whose draft was nested later."""
    if has_published and published_parent_id is None:
        return True
    if has_draft:
        return draft_parent_id is None
    if has_published:
        return published_parent_id is None
    return True
