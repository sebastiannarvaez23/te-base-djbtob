"""FASE 3 — Matriz de evaluación, contexto parcial, resiliencia y defaults.

Consolida el contrato de ``is_enabled`` / ``FlagEvaluator`` sin depender de
dominio de warehouse. Ejecutar:

    pytest core/tests/unit/flags/ platform/tests/unit/release/
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.flags import (
    FlagContext,
    FlagDefinition,
    FlagEvaluator,
    FlagKeys,
    FlagScope,
    FlagStatus,
    FlagType,
    FakeFlagStore,
    ScopeType,
    build_default_registry,
    is_enabled,
)
from core.flags.domain.interfaces import IScopeMatcher
from core.flags.scopes.registry import ScopeMatcherRegistry


KEY = 'flags.suite.demo'


def _flag(
    *,
    status: FlagStatus = FlagStatus.ACTIVE,
    enabled: bool = True,
    scopes: list[FlagScope] | None = None,
) -> FlagDefinition:
    return FlagDefinition(
        key=KEY,
        flag_type=FlagType.RELEASE,
        status=status,
        enabled=enabled,
        scopes=scopes or [],
    )


def _store(flag: FlagDefinition | None = None) -> FakeFlagStore:
    store = FakeFlagStore()
    if flag is not None:
        store.set_flag(flag)
    return store


def _full_ctx() -> FlagContext:
    return FlagContext(
        company_id='co-1',
        user_id='user-1',
        country='Colombia',
        state='Cundinamarca',
        city='Bogotá',
    )


# ── Matriz status × enabled ───────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize('status', list(FlagStatus))
@pytest.mark.parametrize('enabled', [True, False])
def test_status_enabled_matrix_global(status, enabled):
    """Solo ACTIVE + enabled=True enciende (rollout global, sin scopes)."""
    store = _store(_flag(status=status, enabled=enabled, scopes=[]))
    expected = status == FlagStatus.ACTIVE and enabled
    assert is_enabled(KEY, _full_ctx(), store=store) is expected


@pytest.mark.unit
@pytest.mark.parametrize('status', [
    FlagStatus.DRAFT,
    FlagStatus.CERTIFIED,
    FlagStatus.DISABLED,
    FlagStatus.ARCHIVED,
])
def test_non_active_never_true_even_with_scopes_and_enabled(status):
    """Ciclo de vida: estados no ACTIVE nunca devuelven True."""
    store = _store(_flag(
        status=status,
        enabled=True,
        scopes=[FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1')],
    ))
    assert is_enabled(KEY, _full_ctx(), store=store) is False


# ── Scopes: match / no-match / OR ─────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize('scope_type,scope_value,ctx_field,ctx_value,matches', [
    (ScopeType.COMPANY, 'co-1', 'company_id', 'co-1', True),
    (ScopeType.COMPANY, 'co-1', 'company_id', 'co-9', False),
    (ScopeType.USER, 'user-1', 'user_id', 'user-1', True),
    (ScopeType.USER, 'user-1', 'user_id', 'user-9', False),
    (ScopeType.COUNTRY, 'Colombia', 'country', 'Colombia', True),
    (ScopeType.COUNTRY, 'Colombia', 'country', 'Peru', False),
    (ScopeType.STATE, 'Cundinamarca', 'state', 'Cundinamarca', True),
    (ScopeType.STATE, 'Cundinamarca', 'state', 'Antioquia', False),
    (ScopeType.CITY, 'Bogotá', 'city', 'Bogotá', True),
    (ScopeType.CITY, 'Bogotá', 'city', 'Medellín', False),
])
def test_scope_match_matrix(scope_type, scope_value, ctx_field, ctx_value, matches):
    store = _store(_flag(scopes=[
        FlagScope(scope_type=scope_type, scope_value=scope_value),
    ]))
    ctx = FlagContext(**{ctx_field: ctx_value})
    assert is_enabled(KEY, ctx, store=store) is matches


@pytest.mark.unit
def test_or_between_scopes_activates_on_first_match():
    store = _store(_flag(scopes=[
        FlagScope(scope_type=ScopeType.COMPANY, scope_value='other'),
        FlagScope(scope_type=ScopeType.USER, scope_value='user-1'),
        FlagScope(scope_type=ScopeType.CITY, scope_value='Medellín'),
    ]))
    assert is_enabled(KEY, _full_ctx(), store=store) is True


@pytest.mark.unit
def test_or_between_scopes_all_miss_is_false():
    store = _store(_flag(scopes=[
        FlagScope(scope_type=ScopeType.COMPANY, scope_value='other'),
        FlagScope(scope_type=ScopeType.COUNTRY, scope_value='Peru'),
    ]))
    assert is_enabled(KEY, _full_ctx(), store=store) is False


# ── Contexto parcial ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_partial_context_global_flag_still_on():
    store = _store(_flag(scopes=[]))
    empty = FlagContext()
    assert is_enabled(KEY, empty, store=store) is True


@pytest.mark.unit
@pytest.mark.parametrize('scope_type,scope_value', [
    (ScopeType.COMPANY, 'co-1'),
    (ScopeType.USER, 'user-1'),
    (ScopeType.COUNTRY, 'Colombia'),
    (ScopeType.STATE, 'Cundinamarca'),
    (ScopeType.CITY, 'Bogotá'),
])
def test_partial_context_missing_attribute_no_match(scope_type, scope_value):
    store = _store(_flag(scopes=[
        FlagScope(scope_type=scope_type, scope_value=scope_value),
    ]))
    assert is_enabled(KEY, FlagContext(), store=store) is False


# ── Resiliencia ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_store_raising_returns_false_without_propagating():
    store = MagicMock()
    store.get_flag.side_effect = RuntimeError('infra down')

    assert is_enabled(KEY, _full_ctx(), store=store) is False
    # No exception propagates to caller.


@pytest.mark.unit
def test_missing_key_returns_false():
    assert is_enabled(KEY, _full_ctx(), store=FakeFlagStore()) is False


@pytest.mark.unit
def test_matcher_raising_returns_false_without_propagating():
    class BoomMatcher(IScopeMatcher):
        def matches(self, scope, context):
            raise RuntimeError('matcher boom')

    registry = build_default_registry()
    registry.register(ScopeType.COMPANY, BoomMatcher())
    store = _store(_flag(scopes=[
        FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1'),
    ]))

    assert FlagEvaluator(store, registry=registry).is_enabled(KEY, _full_ctx()) is False


@pytest.mark.unit
def test_unregistered_scope_type_is_skipped_not_crash():
    """Scope sin matcher en el registry: se omite; si no hay otro match → False."""
    registry = ScopeMatcherRegistry()  # vacío a propósito
    store = _store(_flag(scopes=[
        FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1'),
    ]))

    assert FlagEvaluator(store, registry=registry).is_enabled(KEY, _full_ctx()) is False


# ── Extensibilidad ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_new_matcher_without_changing_evaluator():
    """Ampliar targeting = registrar matcher; FlagEvaluator no se toca."""

    class AlwaysMatchCompany(IScopeMatcher):
        def matches(self, scope, context):
            return True

    registry = build_default_registry()
    registry.register(ScopeType.COMPANY, AlwaysMatchCompany())

    store = _store(_flag(scopes=[
        FlagScope(scope_type=ScopeType.COMPANY, scope_value='never-equals'),
    ]))

    assert FlagEvaluator(store).is_enabled(KEY, _full_ctx()) is False
    assert FlagEvaluator(store, registry=registry).is_enabled(KEY, _full_ctx()) is True


# ── Defaults / FlagKeys ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_flag_keys_constant_without_store_entry_is_false():
    """Key tipada en código (patrón FlagKeys) sin fila en el store → False."""
    # Convención: declarar en FlagKeys al adoptar una flag; si aún no hay
    # definición persistida (o se archivó), is_enabled cae a lógica antigua.
    key = 'flags.suite.unpersisted'
    FlagKeys.SUITE_UNPERSISTED = key  # simula constante tipada en el registro
    try:
        store = FakeFlagStore()
        assert is_enabled(FlagKeys.SUITE_UNPERSISTED, _full_ctx(), store=store) is False
    finally:
        delattr(FlagKeys, 'SUITE_UNPERSISTED')


@pytest.mark.unit
def test_empty_context_and_missing_flag_is_safe():
    assert is_enabled('no.such.flag', FlagContext(), store=FakeFlagStore()) is False
