"""
Tests de la factory de :class:`IPaymentGateway`.

Se mockea ``core.parameters.get_parameter`` para ejercitar todas las
combinaciones de ``SIMULATE_PAYMENT`` y ``PAYMENT_PROVIDER`` sin
depender de la BD.
"""

from unittest.mock import patch

import pytest

from platform.features.billing.commerce.payments.domain.enums import GatewayProvider
from platform.features.billing.commerce.payments.domain.interfaces import IPaymentGateway
from platform.features.billing.commerce.payments.infrastructure.gateways import factory, registry
from platform.features.billing.commerce.payments.infrastructure.gateways.simulator.gateway import SimulatedGateway


pytestmark = pytest.mark.unit


# ── is_simulation_enabled ─────────────────────────────────────────────────────


def _patch_param(values: dict):
    """
    Devuelve un context manager que mockea ``core.parameters.get_parameter``.

    ``values`` mapea ``code → valor``. Códigos no incluidos devuelven el
    ``default`` que el llamador pasó.
    """
    def fake_get_parameter(code, default=None):
        return values.get(code, default)
    return patch.object(factory, 'get_parameter', side_effect=fake_get_parameter)


def test_simulation_default_true_when_parameter_missing():
    """Sin parámetro en BD, el sistema asume modo simulado (fail-safe)."""
    with _patch_param({}):
        assert factory.is_simulation_enabled() is True


def test_simulation_true_when_parameter_is_true():
    with _patch_param({'SIMULATE_PAYMENT': True}):
        assert factory.is_simulation_enabled() is True


def test_simulation_false_when_parameter_is_false():
    with _patch_param({'SIMULATE_PAYMENT': False}):
        assert factory.is_simulation_enabled() is False


# ── configured_provider ───────────────────────────────────────────────────────


def test_configured_provider_returns_none_when_missing():
    with _patch_param({}):
        assert factory.configured_provider() is None


def test_configured_provider_returns_enum_when_set():
    with _patch_param({'PAYMENT_PROVIDER': 'stripe'}):
        assert factory.configured_provider() == GatewayProvider.STRIPE


def test_configured_provider_is_case_insensitive():
    with _patch_param({'PAYMENT_PROVIDER': 'WOMPI'}):
        assert factory.configured_provider() == GatewayProvider.WOMPI


def test_configured_provider_returns_none_for_unknown_value():
    with _patch_param({'PAYMENT_PROVIDER': 'banana-pay'}):
        assert factory.configured_provider() is None


# ── get_payment_gateway: modo simulado ────────────────────────────────────────


def test_get_payment_gateway_returns_simulator_when_simulation_on():
    with _patch_param({'SIMULATE_PAYMENT': True}):
        gw = factory.get_payment_gateway()
        assert isinstance(gw, SimulatedGateway)
        assert gw.provider == GatewayProvider.SIMULATOR


def test_get_payment_gateway_ignores_provider_argument_when_simulating():
    """En modo simulado nunca devolvemos un provider real — incluso si se pide."""
    with _patch_param({'SIMULATE_PAYMENT': True, 'PAYMENT_PROVIDER': 'stripe'}):
        gw = factory.get_payment_gateway(GatewayProvider.STRIPE)
        assert isinstance(gw, SimulatedGateway)


# ── get_payment_gateway: modo real ────────────────────────────────────────────


def test_get_payment_gateway_raises_when_real_mode_without_provider():
    with _patch_param({'SIMULATE_PAYMENT': False}):
        with pytest.raises(factory.PaymentGatewayUnavailableError) as exc:
            factory.get_payment_gateway()
        assert 'SIMULATE_PAYMENT' in str(exc.value)


def test_get_payment_gateway_raises_when_provider_not_registered():
    """``PAYMENT_PROVIDER=stripe`` configurado pero sin adapter registrado ⇒ error."""
    with _patch_param({'SIMULATE_PAYMENT': False, 'PAYMENT_PROVIDER': 'stripe'}):
        with pytest.raises(factory.PaymentGatewayUnavailableError):
            factory.get_payment_gateway()


def test_get_payment_gateway_resolves_registered_adapter():
    """Cuando hay un adapter registrado, la factory lo instancia."""

    class FakeStripeGateway(IPaymentGateway):
        provider = GatewayProvider.STRIPE
        def create_charge(self, request, idempotency_key): ...
        def confirm_charge(self, gateway_charge_id, payload=None): ...
        def capture_charge(self, gateway_charge_id, amount=None): ...
        def cancel_charge(self, gateway_charge_id, reason=''): ...
        def refund_charge(self, request): ...
        def fetch_charge(self, gateway_charge_id): ...
        def verify_webhook_signature(self, payload_bytes, signature_header): ...
        def parse_webhook_event(self, payload_bytes): ...

    registry.register_gateway(GatewayProvider.STRIPE, FakeStripeGateway)
    try:
        with _patch_param({'SIMULATE_PAYMENT': False, 'PAYMENT_PROVIDER': 'stripe'}):
            gw = factory.get_payment_gateway()
            assert isinstance(gw, FakeStripeGateway)
    finally:
        # Limpiamos para no contaminar otros tests.
        registry._REGISTRY.pop(GatewayProvider.STRIPE, None)


def test_get_payment_gateway_with_explicit_provider_argument():
    """Pasar ``provider`` explícito gana sobre el parámetro configurado."""

    class FakeWompi(IPaymentGateway):
        provider = GatewayProvider.WOMPI
        def create_charge(self, request, idempotency_key): ...
        def confirm_charge(self, gateway_charge_id, payload=None): ...
        def capture_charge(self, gateway_charge_id, amount=None): ...
        def cancel_charge(self, gateway_charge_id, reason=''): ...
        def refund_charge(self, request): ...
        def fetch_charge(self, gateway_charge_id): ...
        def verify_webhook_signature(self, payload_bytes, signature_header): ...
        def parse_webhook_event(self, payload_bytes): ...

    registry.register_gateway(GatewayProvider.WOMPI, FakeWompi)
    try:
        with _patch_param({'SIMULATE_PAYMENT': False, 'PAYMENT_PROVIDER': 'stripe'}):
            gw = factory.get_payment_gateway(GatewayProvider.WOMPI)
            assert isinstance(gw, FakeWompi)
    finally:
        registry._REGISTRY.pop(GatewayProvider.WOMPI, None)


# ── Registry ──────────────────────────────────────────────────────────────────


def test_registry_starts_empty():
    """Por defecto ningún adapter real está registrado."""
    # No depende del orden de ejecución: limpiamos antes.
    snapshot = dict(registry._REGISTRY)
    registry._REGISTRY.clear()
    try:
        assert registry.registered_providers() == []
        assert registry.get_gateway_class(GatewayProvider.STRIPE) is None
    finally:
        registry._REGISTRY.update(snapshot)


def test_register_and_lookup_round_trip():
    class FakeGw(IPaymentGateway):
        provider = GatewayProvider.PAYU
        def create_charge(self, request, idempotency_key): ...
        def confirm_charge(self, gateway_charge_id, payload=None): ...
        def capture_charge(self, gateway_charge_id, amount=None): ...
        def cancel_charge(self, gateway_charge_id, reason=''): ...
        def refund_charge(self, request): ...
        def fetch_charge(self, gateway_charge_id): ...
        def verify_webhook_signature(self, payload_bytes, signature_header): ...
        def parse_webhook_event(self, payload_bytes): ...

    registry.register_gateway(GatewayProvider.PAYU, FakeGw)
    try:
        assert registry.get_gateway_class(GatewayProvider.PAYU) is FakeGw
        assert GatewayProvider.PAYU in registry.registered_providers()
    finally:
        registry._REGISTRY.pop(GatewayProvider.PAYU, None)


def test_register_overrides_existing_entry():
    class A(IPaymentGateway):
        provider = GatewayProvider.PAYU
        def create_charge(self, request, idempotency_key): ...
        def confirm_charge(self, gateway_charge_id, payload=None): ...
        def capture_charge(self, gateway_charge_id, amount=None): ...
        def cancel_charge(self, gateway_charge_id, reason=''): ...
        def refund_charge(self, request): ...
        def fetch_charge(self, gateway_charge_id): ...
        def verify_webhook_signature(self, payload_bytes, signature_header): ...
        def parse_webhook_event(self, payload_bytes): ...

    class B(A):
        pass

    registry.register_gateway(GatewayProvider.PAYU, A)
    registry.register_gateway(GatewayProvider.PAYU, B)
    try:
        assert registry.get_gateway_class(GatewayProvider.PAYU) is B
    finally:
        registry._REGISTRY.pop(GatewayProvider.PAYU, None)
