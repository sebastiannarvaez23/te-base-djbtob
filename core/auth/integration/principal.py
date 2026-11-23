"""Authenticated principal for Integration Applications (not a Django User)."""
from __future__ import annotations

from typing import Sequence


class IntegrationPrincipal:
    """Lightweight identity attached to ``request.user`` by the Bearer authenticator.

    Intentionally is **not** ``registration.User`` or ``AdminUser`` so
    ``IsCompanyMember`` and human-session permissions fail closed unless a
    view explicitly accepts integration auth.
    """

    def __init__(
        self,
        *,
        app_id: str,
        client_id: str,
        schema_name: str,
        scopes: Sequence[str],
        jti: str = '',
        name: str = '',
    ):
        self.app_id = str(app_id)
        self.client_id = client_id
        self.schema_name = schema_name
        self.scopes = frozenset(scopes or ())
        self.jti = jti or ''
        self.name = name or ''

    @property
    def pk(self):
        return self.app_id

    @property
    def id(self):
        return self.app_id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def has_all_scopes(self, required: Sequence[str]) -> bool:
        return frozenset(required).issubset(self.scopes)

    def __str__(self) -> str:
        return f'IntegrationPrincipal({self.client_id})'
