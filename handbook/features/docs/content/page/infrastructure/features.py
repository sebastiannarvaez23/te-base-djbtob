"""Adaptador del catálogo de funcionalidades (mundo platform).

Único punto del handbook que conoce los modelos de funcionalidades: el
resto de la infraestructura consulta por audiencia a través de estas
funciones. Los imports son perezosos para no acoplar la carga de apps.
"""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from django.db.models import Q, QuerySet

from handbook.core.constants import AUDIENCE_ADMIN, AUDIENCE_WMS
from handbook.features.docs.content.page.domain.rules import feature_display, feature_ref


def feature_model(audience: str):
    """Modelo del catálogo de la audiencia, o ``None`` si no tiene catálogo."""
    if audience == AUDIENCE_WMS:
        from platform.features.security.access.functionalities.models import Functionality
        return Functionality
    if audience == AUDIENCE_ADMIN:
        from platform.features.security.access.roles.models import AdminFeature
        return AdminFeature
    return None


def active_features(audience: str) -> QuerySet:
    return feature_model(audience).objects.filter(is_active=True)


def active_feature_keys(revisions: Iterable) -> dict[UUID, str]:
    """Claves de las funcionalidades activas de las revisiones: una consulta por audiencia."""
    refs: dict[str, set[UUID]] = {AUDIENCE_WMS: set(), AUDIENCE_ADMIN: set()}
    for revision in revisions:
        ref = feature_ref(revision.audience, revision.client_feature_id, revision.admin_feature_id)
        if ref is not None:
            refs[revision.audience].add(ref)
    keys: dict[UUID, str] = {}
    for audience, ids in refs.items():
        if ids:
            keys.update(active_features(audience).filter(pk__in=ids).values_list('id', 'key'))
    return keys


def readable_feature(revision, keys: dict[UUID, str]) -> tuple[bool, str | None]:
    """Una página ligada a una funcionalidad inactiva no se publica a lectores."""
    ref = feature_ref(revision.audience, revision.client_feature_id, revision.admin_feature_id)
    if ref is None:
        return True, None
    key = keys.get(ref)
    return key is not None, key


def active_key(audience: str, feature_id: UUID) -> str | None:
    if feature_model(audience) is None:
        return None
    return active_features(audience).filter(pk=feature_id).values_list('key', flat=True).first()


def feature_category(audience: str, feature_id: UUID) -> str | None:
    """Categoría activa de la funcionalidad, o ``None`` si no existe."""
    if feature_model(audience) is None:
        return None
    return active_features(audience).filter(pk=feature_id).values_list('category', flat=True).first()


def feature_label(audience: str, feature_id: UUID | None) -> str:
    """Etiqueta ``label · key`` aunque la funcionalidad esté inactiva (vista de gestión)."""
    model = feature_model(audience)
    if feature_id is None or model is None:
        return ''
    row = model.objects.filter(pk=feature_id).values_list('label', 'key').first()
    return feature_display(*row) if row else ''


def bound_to_key(feature_key: str) -> Q:
    """Revisiones publicadas ligadas a la funcionalidad activa ``feature_key``."""
    return (
        Q(
            published_revision__audience=AUDIENCE_WMS,
            published_revision__client_feature_id__in=active_features(AUDIENCE_WMS)
            .filter(key=feature_key).values('id'),
        )
        | Q(
            published_revision__audience=AUDIENCE_ADMIN,
            published_revision__admin_feature_id__in=active_features(AUDIENCE_ADMIN)
            .filter(key=feature_key).values('id'),
        )
    )


def search_features(audience: str, query: str, *, category: str | None = None) -> QuerySet:
    rows = active_features(audience).select_related('module')
    if category:
        rows = rows.filter(category=category)
    if query:
        rows = rows.filter(
            Q(key__icontains=query) | Q(label__icontains=query) | Q(module__name__icontains=query),
        )
    return rows.order_by('key')
