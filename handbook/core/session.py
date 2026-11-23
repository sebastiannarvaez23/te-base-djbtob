"""Carga de feature keys de sesión para construir un HandbookViewer."""

from __future__ import annotations

from typing import FrozenSet, Optional, Protocol

from handbook.core.viewer import HandbookViewer


class IHandbookFeatureLoader(Protocol):
    def load_admin_features(self, user) -> FrozenSet[str]:
        ...

    def load_client_features(self, user) -> FrozenSet[str]:
        ...


class SessionFeatureLoader:
    """Usa los use cases de sesión ya existentes (admin / tenant)."""

    def load_admin_features(self, user) -> FrozenSet[str]:
        from platform.features.security.auth.auth.application.use_cases import (
            BuildAdminSessionUseCase,
        )
        from platform.features.security.auth.auth.infrastructure.repositories import (
            DjangoAdminSessionRepository,
        )

        session = BuildAdminSessionUseCase(DjangoAdminSessionRepository()).execute(user)
        return frozenset(session.features or [])

    def load_client_features(self, user) -> FrozenSet[str]:
        from client.features.security.lifecycle.auth.application.use_cases import (
            BuildSessionUseCase,
        )
        from client.features.security.lifecycle.auth.infrastructure.repositories import (
            DjangoSessionRepository,
        )

        session = BuildSessionUseCase(DjangoSessionRepository()).execute(user)
        return frozenset(session.features or [])


def viewer_from_user(
    user,
    *,
    payload: Optional[dict] = None,
    loader: Optional[IHandbookFeatureLoader] = None,
) -> HandbookViewer:
    """Construye el viewer a partir de un usuario autenticado.

    ``payload`` es el JWT (``request.auth``) — lleva ``user_type`` y ``schema_name``.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return HandbookViewer.anonymous()

    payload = payload or {}
    user_type = payload.get('user_type')
    loader = loader or SessionFeatureLoader()

    if user_type == 'client' or _is_tenant_user(user, user_type):
        schema_name = payload.get('schema_name') or ''
        features = _client_features(user, schema_name, loader)
        return HandbookViewer.client(
            user_id=str(user.pk),
            features=features,
            schema_name=schema_name or None,
        )

    features = loader.load_admin_features(user)
    return HandbookViewer.admin(
        user_id=str(user.pk),
        features=features,
        is_superuser=bool(getattr(user, 'is_superuser', False)),
    )


def resolve_viewer(request, *, loader: Optional[IHandbookFeatureLoader] = None) -> HandbookViewer:
    cached = getattr(request, '_handbook_viewer', None)
    if cached is not None:
        return cached

    user = getattr(request, 'user', None)
    authenticated = bool(user) and getattr(user, 'is_authenticated', False)
    if not authenticated:
        viewer = HandbookViewer.anonymous()
    else:
        payload = getattr(request, 'auth', None)
        if not isinstance(payload, dict):
            payload = {}
        viewer = viewer_from_user(user, payload=payload, loader=loader)

    request._handbook_viewer = viewer
    return viewer


def _is_tenant_user(user, user_type: Optional[str]) -> bool:
    if user_type == 'admin':
        return False
    return getattr(user, 'company_id', None) is not None


def _client_features(user, schema_name: str, loader: IHandbookFeatureLoader) -> FrozenSet[str]:
    if not schema_name or schema_name == 'public':
        return loader.load_client_features(user)

    from django_tenants.utils import schema_context

    with schema_context(schema_name):
        return loader.load_client_features(user)
