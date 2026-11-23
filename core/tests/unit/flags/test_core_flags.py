"""Unit tests para el módulo transversal core/flags (FASE 1).

Fijan el contrato de evaluación de release flags:
- Matchers por COMPANY / USER / COUNTRY / STATE / CITY.
- FlagEvaluator: estados, global, scopes OR, key desconocida, fail-safe.
- FlagContext.from_request.
- Facade is_enabled + FakeFlagStore intercambiable.
- Extensibilidad del registry sin tocar el evaluador.
"""

from __future__ import annotations

from types import SimpleNamespace
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
    get_flag_store,
    is_enabled,
)
from core.flags.domain.interfaces import IScopeMatcher
from core.flags.infrastructure.fake_store import FakeFlagStore as FakeStoreClass
from core.flags.scopes import (
    CityScopeMatcher,
    CompanyScopeMatcher,
    CountryScopeMatcher,
    StateScopeMatcher,
    UserScopeMatcher,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_flag(
    key: str = 'demo.feature',
    *,
    enabled: bool = True,
    scopes: list[FlagScope] | None = None,
    status: FlagStatus = FlagStatus.ACTIVE,
) -> FlagDefinition:
    return FlagDefinition(
        key=key,
        flag_type=FlagType.RELEASE,
        status=status,
        enabled=enabled,
        scopes=scopes or [],
    )


def _ctx(**kwargs) -> FlagContext:
    defaults = dict(
        company_id='co-1',
        user_id='user-1',
        country='Colombia',
        state='Cundinamarca',
        city='Bogotá',
    )
    defaults.update(kwargs)
    return FlagContext(**defaults)


# ── Matchers ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCompanyScopeMatcher:

    def test_match(self):
        scope = FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1')
        assert CompanyScopeMatcher().matches(scope, _ctx()) is True

    def test_no_match(self):
        scope = FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-2')
        assert CompanyScopeMatcher().matches(scope, _ctx()) is False

    def test_missing_context_attribute(self):
        scope = FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1')
        assert CompanyScopeMatcher().matches(scope, _ctx(company_id=None)) is False


@pytest.mark.unit
class TestUserScopeMatcher:

    def test_match(self):
        scope = FlagScope(scope_type=ScopeType.USER, scope_value='user-1')
        assert UserScopeMatcher().matches(scope, _ctx()) is True

    def test_no_match(self):
        scope = FlagScope(scope_type=ScopeType.USER, scope_value='user-9')
        assert UserScopeMatcher().matches(scope, _ctx()) is False

    def test_missing_context_attribute(self):
        scope = FlagScope(scope_type=ScopeType.USER, scope_value='user-1')
        assert UserScopeMatcher().matches(scope, _ctx(user_id=None)) is False


@pytest.mark.unit
class TestCountryScopeMatcher:

    def test_match_case_insensitive(self):
        scope = FlagScope(scope_type=ScopeType.COUNTRY, scope_value='colombia')
        assert CountryScopeMatcher().matches(scope, _ctx(country='Colombia')) is True

    def test_no_match(self):
        scope = FlagScope(scope_type=ScopeType.COUNTRY, scope_value='Peru')
        assert CountryScopeMatcher().matches(scope, _ctx()) is False

    def test_missing_context_attribute(self):
        scope = FlagScope(scope_type=ScopeType.COUNTRY, scope_value='Colombia')
        assert CountryScopeMatcher().matches(scope, _ctx(country=None)) is False


@pytest.mark.unit
class TestStateScopeMatcher:

    def test_match(self):
        scope = FlagScope(scope_type=ScopeType.STATE, scope_value='Cundinamarca')
        assert StateScopeMatcher().matches(scope, _ctx()) is True

    def test_no_match(self):
        scope = FlagScope(scope_type=ScopeType.STATE, scope_value='Antioquia')
        assert StateScopeMatcher().matches(scope, _ctx()) is False

    def test_missing_context_attribute(self):
        scope = FlagScope(scope_type=ScopeType.STATE, scope_value='Cundinamarca')
        assert StateScopeMatcher().matches(scope, _ctx(state=None)) is False


@pytest.mark.unit
class TestCityScopeMatcher:

    def test_match(self):
        scope = FlagScope(scope_type=ScopeType.CITY, scope_value='Bogotá')
        assert CityScopeMatcher().matches(scope, _ctx()) is True

    def test_no_match(self):
        scope = FlagScope(scope_type=ScopeType.CITY, scope_value='Medellín')
        assert CityScopeMatcher().matches(scope, _ctx()) is False

    def test_missing_context_attribute(self):
        scope = FlagScope(scope_type=ScopeType.CITY, scope_value='Bogotá')
        assert CityScopeMatcher().matches(scope, _ctx(city=None)) is False


# ── Evaluator ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestFlagEvaluator:

    def _eval(self, flag: FlagDefinition, ctx: FlagContext | None = None) -> bool:
        store = FakeFlagStore()
        store.set_flag(flag)
        return FlagEvaluator(store).is_enabled(flag.key, ctx or _ctx())

    def test_draft_is_false(self):
        assert self._eval(_active_flag(status=FlagStatus.DRAFT, enabled=True)) is False

    def test_disabled_status_is_false(self):
        assert self._eval(_active_flag(status=FlagStatus.DISABLED, enabled=True)) is False

    def test_certified_is_false(self):
        assert self._eval(_active_flag(status=FlagStatus.CERTIFIED, enabled=True)) is False

    def test_archived_is_false(self):
        assert self._eval(_active_flag(status=FlagStatus.ARCHIVED, enabled=True)) is False

    def test_active_but_not_enabled_is_false(self):
        assert self._eval(_active_flag(enabled=False)) is False

    def test_active_global_no_scopes(self):
        assert self._eval(_active_flag(scopes=[])) is True

    def test_active_company_scope(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1'),
        ])
        assert self._eval(flag) is True
        assert self._eval(flag, _ctx(company_id='other')) is False

    def test_active_user_scope(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.USER, scope_value='user-1'),
        ])
        assert self._eval(flag) is True

    def test_active_country_scope(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.COUNTRY, scope_value='Colombia'),
        ])
        assert self._eval(flag) is True

    def test_active_state_scope(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.STATE, scope_value='Cundinamarca'),
        ])
        assert self._eval(flag) is True

    def test_active_city_scope(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.CITY, scope_value='Bogotá'),
        ])
        assert self._eval(flag) is True

    def test_or_between_scopes(self):
        flag = _active_flag(scopes=[
            FlagScope(scope_type=ScopeType.COMPANY, scope_value='other-co'),
            FlagScope(scope_type=ScopeType.COUNTRY, scope_value='Colombia'),
        ])
        assert self._eval(flag) is True

    def test_inactive_scope_ignored(self):
        flag = _active_flag(scopes=[
            FlagScope(
                scope_type=ScopeType.COMPANY,
                scope_value='co-1',
                is_active=False,
            ),
        ])
        # No active scopes left → global ON
        assert self._eval(flag) is True

    def test_unknown_key_is_false(self):
        store = FakeFlagStore()
        assert FlagEvaluator(store).is_enabled('missing.key', _ctx()) is False

    def test_store_exception_is_false(self):
        store = MagicMock()
        store.get_flag.side_effect = RuntimeError('redis down')
        assert FlagEvaluator(store).is_enabled('any.key', _ctx()) is False


# ── FlagContext.from_request ──────────────────────────────────────────────────

@pytest.mark.unit
class TestFlagContextFromRequest:

    def test_full_request(self):
        company = SimpleNamespace(
            id='co-99',
            geo_city=SimpleNamespace(
                name='Lima',
                department=SimpleNamespace(
                    name='Lima',
                    country=SimpleNamespace(name='Peru'),
                ),
            ),
        )
        user = SimpleNamespace(id='u-7', is_authenticated=True)
        request = SimpleNamespace(tenant=company, user=user)

        ctx = FlagContext.from_request(request)
        assert ctx.company_id == 'co-99'
        assert ctx.user_id == 'u-7'
        assert ctx.country == 'Peru'
        assert ctx.state == 'Lima'
        assert ctx.city == 'Lima'

    def test_without_tenant(self):
        user = SimpleNamespace(id='u-1', is_authenticated=True)
        request = SimpleNamespace(user=user)
        ctx = FlagContext.from_request(request)
        assert ctx.company_id is None
        assert ctx.country is None
        assert ctx.user_id == 'u-1'

    def test_without_user(self):
        company = SimpleNamespace(
            id='co-1',
            geo_city=SimpleNamespace(
                name='Y',
                department=SimpleNamespace(
                    name='X',
                    country=SimpleNamespace(name='Colombia'),
                ),
            ),
        )
        request = SimpleNamespace(tenant=company)
        ctx = FlagContext.from_request(request)
        assert ctx.company_id == 'co-1'
        assert ctx.user_id is None

    def test_unauthenticated_user(self):
        company = SimpleNamespace(
            id='co-1',
            geo_city=SimpleNamespace(
                name='Y',
                department=SimpleNamespace(
                    name='X',
                    country=SimpleNamespace(name='Colombia'),
                ),
            ),
        )
        user = SimpleNamespace(id='u-1', is_authenticated=False)
        request = SimpleNamespace(tenant=company, user=user)
        ctx = FlagContext.from_request(request)
        assert ctx.user_id is None


# ── Facade / factory / extensibility ──────────────────────────────────────────

@pytest.mark.unit
class TestFacadeAndFactory:

    def test_fake_provider(self):
        assert isinstance(get_flag_store('fake'), FakeStoreClass)

    def test_is_enabled_with_injected_store(self):
        store = FakeFlagStore()
        store.set_flag(_active_flag(key='demo.feature'))
        assert is_enabled('demo.feature', _ctx(), store=store) is True

    def test_is_enabled_unknown_defaults_to_legacy(self):
        store = FakeFlagStore()
        assert is_enabled('no.such.flag', _ctx(), store=store) is False

    def test_use_case_style_branching(self):
        """Simula el patrón de consumo en un use case."""
        KEY = 'picking.route_v2'
        store = FakeFlagStore()
        store.set_flag(_active_flag(key=KEY, scopes=[
            FlagScope(scope_type=ScopeType.COMPANY, scope_value='co-1'),
        ]))

        def execute(ctx: FlagContext) -> str:
            if is_enabled(KEY, ctx, store=store):
                return 'new'
            return 'legacy'

        assert execute(_ctx(company_id='co-1')) == 'new'
        assert execute(_ctx(company_id='co-2')) == 'legacy'

    def test_flag_keys_is_importable(self):
        assert FlagKeys is not None


@pytest.mark.unit
class TestRegistryExtensibility:

    def test_custom_scope_type_without_changing_evaluator(self):
        """Registrar un matcher nuevo basta para extender el espectro."""
        # ScopeType no tiene REGION; usamos un enum member existente re-mapeado
        # en un registry propio, o un matcher custom sobre COMPANY para probar
        # el mecanismo de registro. Aquí registramos un matcher que siempre
        # matchea sobre CITY en un registry aislado.
        class AlwaysOnCityMatcher(IScopeMatcher):
            def matches(self, scope, context):
                return True

        registry = build_default_registry()
        registry.register(ScopeType.CITY, AlwaysOnCityMatcher())

        store = FakeFlagStore()
        store.set_flag(_active_flag(scopes=[
            FlagScope(scope_type=ScopeType.CITY, scope_value='no-match-city'),
        ]))

        # Con matcher default no matchearía; con el custom sí.
        assert FlagEvaluator(store).is_enabled('demo.feature', _ctx()) is False
        assert FlagEvaluator(store, registry=registry).is_enabled(
            'demo.feature', _ctx(),
        ) is True
