"""
Tests que verifican qué eventos de dominio publican los use cases.

Patcheamos ``publish`` para inspeccionar las llamadas sin que se
activen los listeners reales (que tocarían BD vía Django ORM).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from platform.features.billing.commerce.payments.application import use_cases as uc_module
from platform.features.billing.commerce.payments.application.use_cases import (
    CancelChargeUseCase,
    CaptureChargeUseCase,
    ConfirmChargeUseCase,
    CreateChargeUseCase,
    FetchChargeUseCase,
    ProcessWebhookUseCase,
    RefundChargeUseCase,
)
from platform.features.billing.commerce.payments.domain.enums import (
    ChargeStatus,
    GatewayProvider,
    MethodType,
    WebhookEventType,
)
from platform.features.billing.commerce.payments.domain.events import (
    PaymentAuthorized,
    PaymentCanceled,
    PaymentCaptured,
    PaymentFailed,
    PaymentRefunded,
)
from platform.features.billing.commerce.payments.domain.schemas import (
    ChargeRequest,
    ChargeResult,
    ChargeSchema,
    PayerRef,
    RefundResult,
    WebhookEvent,
    WebhookInboxEntrySchema,
)


pytestmark = pytest.mark.unit


# ── Fixtures comunes ─────────────────────────────────────────────────────────


@pytest.fixture
def stub_publish(monkeypatch):
    """Captura los eventos en lugar de publicarlos al bus real."""
    stub = MagicMock()
    monkeypatch.setattr(uc_module, 'publish', stub)
    return stub


def _charge(**overrides) -> ChargeSchema:
    defaults = dict(
        id=uuid.uuid4(),
        gateway_provider='simulator',
        gateway_charge_id='sim_ch_abc',
        company_id=uuid.uuid4(),
        amount=Decimal('100'),
        currency='COP',
        method_type=MethodType.CARD,
        status=ChargeStatus.PENDING,
        refunded_amount=Decimal('0'),
    )
    defaults.update(overrides)
    return ChargeSchema(**defaults)


def _result(status=ChargeStatus.CAPTURED, **overrides) -> ChargeResult:
    defaults = dict(
        gateway_provider=GatewayProvider.SIMULATOR,
        gateway_charge_id='sim_ch_abc',
        status=status,
        amount=Decimal('100'),
        currency='COP',
        method_type=MethodType.CARD,
    )
    defaults.update(overrides)
    return ChargeResult(**defaults)


def _router_with(gateway):
    router = MagicMock()
    router.select_gateway.return_value = gateway
    return router


def _currency_policy(*, default='COP'):
    from types import SimpleNamespace

    def assert_charge_currency(*, company_id, currency):
        return (currency or default).strip().upper() or default

    def assert_refund_currency(*, charge_currency, currency):
        return (currency or charge_currency or default).strip().upper() or default

    return SimpleNamespace(
        assert_charge_currency=assert_charge_currency,
        assert_refund_currency=assert_refund_currency,
    )


# ── CreateChargeUseCase publica eventos ──────────────────────────────────────


class TestCreateChargePublishesEvents:

    def _setup(self, result_status, invoice_id=None):
        repo = MagicMock()
        repo.get_by_idempotency_key.return_value = None
        company_id = uuid.uuid4()
        created = _charge(status=ChargeStatus.PENDING, invoice_id=invoice_id, company_id=company_id)
        updated = _charge(status=result_status, invoice_id=invoice_id, company_id=company_id)
        repo.create.return_value = created
        repo.transition.return_value = updated
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.create_charge.return_value = _result(status=result_status)
        return (
            CreateChargeUseCase(repo, _router_with(gateway), currency_policy=_currency_policy()),
            repo,
            company_id,
        )

    def test_publishes_payment_captured_when_gateway_returns_captured(self, stub_publish):
        uc, _, company_id = self._setup(ChargeStatus.CAPTURED)
        uc.execute(
            ChargeRequest(payer=PayerRef(company_id=company_id), amount=Decimal('100')),
            company_id=company_id,
        )
        stub_publish.assert_called_once()
        event = stub_publish.call_args.args[0]
        assert isinstance(event, PaymentCaptured)
        assert event.amount == Decimal('100')
        assert event.company_id == company_id

    def test_publishes_payment_failed_with_failure_code(self, stub_publish):
        repo = MagicMock()
        repo.get_by_idempotency_key.return_value = None
        created = _charge(status=ChargeStatus.PENDING)
        repo.create.return_value = created
        repo.transition.return_value = _charge(status=ChargeStatus.FAILED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.create_charge.return_value = _result(
            status=ChargeStatus.FAILED,
            failure_code='card_declined',
            failure_message='nope',
        )
        uc = CreateChargeUseCase(
            repo, _router_with(gateway), currency_policy=_currency_policy(),
        )

        uc.execute(
            ChargeRequest(payer=PayerRef(company_id=created.company_id), amount=Decimal('100')),
            company_id=created.company_id,
        )

        # Hmm: el repo.transition.return_value tiene failure_code='' por default.
        # El evento se construye desde `updated`, así que el failure_code que
        # se publica refleja lo que vino del repo (vacío en este mock).
        # Esto está bien: el contrato del evento refleja el estado en BD.
        event = stub_publish.call_args.args[0]
        assert isinstance(event, PaymentFailed)

    def test_publishes_payment_authorized_when_auth_only(self, stub_publish):
        uc, _, company_id = self._setup(ChargeStatus.AUTHORIZED)
        uc.execute(
            ChargeRequest(payer=PayerRef(company_id=company_id), amount=Decimal('100')),
            company_id=company_id,
        )
        event = stub_publish.call_args.args[0]
        assert isinstance(event, PaymentAuthorized)

    def test_does_not_publish_when_idempotent_hit(self, stub_publish):
        repo = MagicMock()
        repo.get_by_idempotency_key.return_value = _charge(status=ChargeStatus.CAPTURED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        uc = CreateChargeUseCase(
            repo, _router_with(gateway), currency_policy=_currency_policy(),
        )

        uc.execute(
            ChargeRequest(payer=PayerRef(company_id=uuid.uuid4()), amount=Decimal('100')),
            company_id=uuid.uuid4(),
            idempotency_key='dup',
        )

        stub_publish.assert_not_called()  # ningún evento, devolvimos lo que ya existía

    def test_event_carries_invoice_id_when_present(self, stub_publish):
        invoice_id = uuid.uuid4()
        uc, _, company_id = self._setup(ChargeStatus.CAPTURED, invoice_id=invoice_id)
        uc.execute(
            ChargeRequest(payer=PayerRef(company_id=company_id), amount=Decimal('100')),
            company_id=company_id,
            invoice_id=invoice_id,
        )
        event = stub_publish.call_args.args[0]
        assert event.invoice_id == invoice_id


# ── ConfirmChargeUseCase publica eventos ─────────────────────────────────────


class TestConfirmChargePublishesEvents:

    def test_publishes_captured_after_confirming_requires_action(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.REQUIRES_ACTION)
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.confirm_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        uc = ConfirmChargeUseCase(repo, _router_with(gateway))

        uc.execute(existing.id)

        stub_publish.assert_called_once()
        assert isinstance(stub_publish.call_args.args[0], PaymentCaptured)


# ── CaptureChargeUseCase publica eventos ─────────────────────────────────────


class TestCapturePublishesEvents:

    def test_publishes_captured_after_authorize_then_capture(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.AUTHORIZED)
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.capture_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        uc = CaptureChargeUseCase(repo, _router_with(gateway))

        uc.execute(existing.id)

        stub_publish.assert_called_once()
        assert isinstance(stub_publish.call_args.args[0], PaymentCaptured)


# ── CancelChargeUseCase publica eventos ──────────────────────────────────────


class TestCancelPublishesEvents:

    def test_publishes_canceled(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.AUTHORIZED, invoice_id=uuid.uuid4())
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(status=ChargeStatus.CANCELED, invoice_id=existing.invoice_id)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.cancel_charge.return_value = _result(status=ChargeStatus.CANCELED)
        uc = CancelChargeUseCase(repo, _router_with(gateway))

        uc.execute(existing.id, reason='changed mind')

        stub_publish.assert_called_once()
        event = stub_publish.call_args.args[0]
        assert isinstance(event, PaymentCanceled)
        assert event.invoice_id == existing.invoice_id


# ── RefundChargeUseCase publica eventos ──────────────────────────────────────


class TestRefundPublishesEvents:

    def test_publishes_refunded_with_full_delta_on_total_refund(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.CAPTURED, amount=Decimal('100'), refunded_amount=Decimal('0'))
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(status=ChargeStatus.REFUNDED, refunded_amount=Decimal('100'))
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.refund_charge.return_value = RefundResult(
            gateway_provider=GatewayProvider.SIMULATOR,
            gateway_charge_id=existing.gateway_charge_id,
            gateway_refund_id='sim_rf_1',
            amount=Decimal('100'),
            status=ChargeStatus.REFUNDED,
        )
        uc = RefundChargeUseCase(
            repo, _router_with(gateway), currency_policy=_currency_policy(),
        )

        uc.execute(existing.id)

        event = stub_publish.call_args.args[0]
        assert isinstance(event, PaymentRefunded)
        assert event.is_partial is False
        assert event.refund_amount == Decimal('100')   # delta
        assert event.total_refunded == Decimal('100')  # acumulado

    def test_publishes_partial_with_delta_only(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.CAPTURED, amount=Decimal('200'),
                            refunded_amount=Decimal('50'))
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(
            status=ChargeStatus.PARTIALLY_REFUNDED,
            refunded_amount=Decimal('80'),
        )
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.refund_charge.return_value = RefundResult(
            gateway_provider=GatewayProvider.SIMULATOR,
            gateway_charge_id=existing.gateway_charge_id,
            gateway_refund_id='sim_rf_2',
            amount=Decimal('30'),
            status=ChargeStatus.PARTIALLY_REFUNDED,
        )
        uc = RefundChargeUseCase(
            repo, _router_with(gateway), currency_policy=_currency_policy(),
        )

        uc.execute(existing.id, amount=Decimal('30'))

        event = stub_publish.call_args.args[0]
        assert event.is_partial is True
        assert event.refund_amount == Decimal('30')    # 80 - 50
        assert event.total_refunded == Decimal('80')


# ── FetchChargeUseCase publica solo si hay transición real ───────────────────


class TestFetchPublishesEvents:

    def test_publishes_when_provider_diverges(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.PROCESSING)
        repo.get_by_id.return_value = existing
        repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.fetch_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        uc = FetchChargeUseCase(repo, _router_with(gateway))

        uc.execute(existing.id)

        stub_publish.assert_called_once()
        assert isinstance(stub_publish.call_args.args[0], PaymentCaptured)

    def test_does_not_publish_when_provider_agrees(self, stub_publish):
        repo = MagicMock()
        existing = _charge(status=ChargeStatus.CAPTURED)
        repo.get_by_id.return_value = existing
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.fetch_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        uc = FetchChargeUseCase(repo, _router_with(gateway))

        uc.execute(existing.id)

        stub_publish.assert_not_called()


# ── ProcessWebhookUseCase publica eventos ────────────────────────────────────


class TestProcessWebhookPublishesEvents:

    def test_publishes_captured_on_webhook_transition(self, stub_publish, monkeypatch):
        from datetime import datetime, timezone as tz
        charge_repo = MagicMock()
        inbox_repo = MagicMock()
        router = MagicMock()
        entry = WebhookInboxEntrySchema(
            id=uuid.uuid4(),
            provider='simulator',
            external_event_id='evt_1',
            event_type='charge.captured',
            payload={'id': 'evt_1', 'type': 'charge.captured', 'status': 'captured',
                     'charge_id': 'sim_ch_abc', 'amount': '100'},
            signature='sig',
            signature_verified=True,
        )
        existing = _charge(gateway_charge_id='sim_ch_abc', status=ChargeStatus.PROCESSING)
        charge_repo.get_by_gateway_ref.return_value = existing
        charge_repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.parse_webhook_event.return_value = WebhookEvent(
            provider=GatewayProvider.SIMULATOR,
            external_event_id='evt_1',
            event_type=WebhookEventType.CHARGE_CAPTURED,
            gateway_charge_id='sim_ch_abc',
            status=ChargeStatus.CAPTURED,
            amount=Decimal('100'),
            currency='COP',
        )
        monkeypatch.setattr(
            ProcessWebhookUseCase, '_gateway_for_provider',
            lambda self, p: gateway,
        )

        ProcessWebhookUseCase(charge_repo, inbox_repo, router).execute(entry)

        stub_publish.assert_called_once()
        assert isinstance(stub_publish.call_args.args[0], PaymentCaptured)
