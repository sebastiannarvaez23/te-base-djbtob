"""Integration Application OAuth scopes.

A scope is the key of an API-category functionality of the tenant catalog
(``category='api'``). Which keys exist, and which a tenant or user may grant,
comes from ``IIntegrationScopeCatalog``; these helpers stay pure.
"""
from __future__ import annotations

from typing import Iterable


def normalize_scope_keys(scopes: Iterable[str]) -> list[str]:
    """Sorted unique non-empty keys."""
    return sorted({str(s).strip() for s in scopes if s and str(s).strip()})


def disallowed_scopes(scopes: Iterable[str], allowed: Iterable[str]) -> list[str]:
    """Keys in ``scopes`` that are not part of ``allowed`` (sorted)."""
    allowed_set = set(allowed)
    return [s for s in normalize_scope_keys(scopes) if s not in allowed_set]


def parse_scope_string(scope: str | None) -> list[str]:
    """OAuth2 space-delimited scope parameter → list."""
    if not scope or not str(scope).strip():
        return []
    return [part for part in str(scope).split() if part]
