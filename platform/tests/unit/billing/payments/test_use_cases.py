"""
Unit tests para los use cases del módulo de pagos.

Repositorios, router y gateway se mockean con :class:`MagicMock`. Estos
tests prueban orquestación: que cada use case llame al gateway, registre
el attempt, aplique la transición y propague errores correctamente.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from core.errors import (
    AppErrorCode,
    AppException,
    ConflictException,
    NotFoundException,
    ServerException,
    ValidationAppException,
)

from platform.features.billing.commerce.payments.application.use_cases import (
    CancelChargeUseCase,
    CaptureChargeUseCase,
    ConfirmChargeUseCase,
    CreateChargeUseCase,
    FetchChargeUseCase,
    GetChargeByIdUseCase,
    GetChargesByCompanyUseCase,
    ProcessWebhookUseCase,
    RefundChargeUseCase,
)
from platform.features.billing.commerce.payments.domain.enums import (
    AttemptOperation,
    AttemptResult,
    ChargeStatus,
    GatewayProvider,
    MethodType,
    WebhookEventType,
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
from platform.features.billing.commerce.payments.domain.state_machine import InvalidChargeTransitionError


pytestmark = pytest.mark.unit


# ── Helpers de fixtures ───────────────────────────────────────────────────────


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


def _request(**overrides) -> ChargeRequest:
    defaults = dict(
        payer=PayerRef(company_id=uuid.uuid4()),
        amount=Decimal('100'),
        currency='COP',
        method_type=MethodType.CARD,
    )
    defaults.update(overrides)
    return ChargeRequest(**defaults)


def _router_returning(gateway):
    router = MagicMock()
    router.select_gateway.return_value = gateway
    return router


def _currency_policy(*, default='COP', allowed=None):
    """Permissive fake for Create/Refund charge tests.

    Plain object (not MagicMock): MagicMock treats ``assert_*`` as assertions.
    """
    from types import SimpleNamespace

    allowed = set(allowed or ('COP', 'USD'))

    def assert_charge(*, company_id, currency):
        code = (currency or default).strip().upper() or default
        if code not in allowed:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_NOT_ALLOWED)
        return code

    def assert_refund(*, charge_currency, currency):
        charge_code = (charge_currency or '').strip().upper()
        refund_code = (currency or charge_code).strip().upper()
        if not charge_code or refund_code != charge_code:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_MISMATCH)
        return refund_code

    return SimpleNamespace(
        assert_charge_currency=assert_charge,
        default_currency_for_company=lambda company_id: default,
        assert_refund_currency=assert_refund,
    )


# ── GetChargeByIdUseCase ──────────────────────────────────────────────────────


class TestGetChargeByIdUseCase:

    def test_returns_charge_when_found(self):
        repo = MagicMock()
        existing = _charge()
        repo.get_by_id.return_value = existing

        result = GetChargeByIdUseCase(repo).execute(existing.id)

        assert result is existing
        repo.get_by_id.assert_called_once_with(existing.id)

    def test_raises_not_found_when_missing(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException) as exc_info:
            GetChargeByIdUseCase(repo).execute(uuid.uuid4())
        assert exc_info.value.code == AppErrorCode.PAY_CHARGE_NOT_FOUND


# ── GetChargesByCompanyUseCase ────────────────────────────────────────────────


class TestGetChargesByCompanyUseCase:

    def test_returns_list_for_company(self):
        from core.query.core import PaginatedQuery, PaginatedResult

        repo = MagicMock()
        company_id = uuid.uuid4()
        charges = [_charge(company_id=company_id) for _ in range(3)]
        query = PaginatedQuery(page=0, page_size=20, filters={})
        repo.list_by_company.return_value = PaginatedResult(
            items=charges, total=3, page=0, page_size=20, total_pages=1,
        )

        result = GetChargesByCompanyUseCase(repo).execute(company_id, query)

        assert len(result.items) == 3
        repo.list_by_company.assert_called_once_with(company_id, query)

    def test_returns_empty_list_when_company_has_no_charges(self):
        from core.query.core import PaginatedQuery, PaginatedResult

        repo = MagicMock()
        query = PaginatedQuery(page=0, page_size=20, filters={})
        repo.list_by_company.return_value = PaginatedResult(
            items=[], total=0, page=0, page_size=20, total_pages=0,
        )
        result = GetChargesByCompanyUseCase(repo).execute(uuid.uuid4(), query)
        assert result.items == []


# ── CreateChargeUseCase ───────────────────────────────────────────────────────


class TestCreateChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.policy = _currency_policy()
        self.uc = CreateChargeUseCase(
            self.repo, self.router, currency_policy=self.policy,
        )
        self.company_id = uuid.uuid4()

    def test_creates_charge_and_returns_captured_on_success(self):
        created = _charge(company_id=self.company_id)
        updated = _charge(company_id=self.company_id, status=ChargeStatus.CAPTURED)
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.return_value = updated

        result = self.uc.execute(_request(), company_id=self.company_id, idempotency_key='k1')

        assert result.status == ChargeStatus.CAPTURED
        self.repo.create.assert_called_once()
        self.gateway.create_charge.assert_called_once()
        self.repo.add_attempt.assert_called_once()
        attempt = self.repo.add_attempt.call_args.args[0]
        assert attempt.operation == AttemptOperation.CREATE
        assert attempt.result == AttemptResult.SUCCEEDED

    def test_returns_existing_charge_when_idempotency_key_matches(self):
        existing = _charge(status=ChargeStatus.CAPTURED)
        self.repo.get_by_idempotency_key.return_value = existing

        result = self.uc.execute(_request(), company_id=self.company_id, idempotency_key='dup')

        assert result is existing
        self.repo.create.assert_not_called()
        self.gateway.create_charge.assert_not_called()

    def test_no_idempotency_lookup_when_key_not_provided(self):
        created = _charge()
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result()
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        self.uc.execute(_request(), company_id=self.company_id)

        self.repo.get_by_idempotency_key.assert_not_called()

    def test_records_failed_attempt_when_gateway_raises(self):
        created = _charge()
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.side_effect = ConnectionError('provider down')

        with pytest.raises(ServerException) as exc:
            self.uc.execute(_request(), company_id=self.company_id, idempotency_key='k1')

        assert exc.value.code == AppErrorCode.PAY_PROVIDER_ERROR
        # Attempt registrado como FAILED.
        self.repo.add_attempt.assert_called_once()
        attempt = self.repo.add_attempt.call_args.args[0]
        assert attempt.result == AttemptResult.FAILED
        assert 'provider down' in attempt.error_message
        # No se intentó transicionar.
        self.repo.transition.assert_not_called()

    def test_persists_decline_outcome_as_failed_status(self):
        created = _charge()
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result(
            status=ChargeStatus.FAILED,
            failure_code='card_declined',
            failure_message='nope',
        )
        self.repo.transition.return_value = _charge(status=ChargeStatus.FAILED)

        result = self.uc.execute(_request(), company_id=self.company_id, idempotency_key='k1')

        assert result.status == ChargeStatus.FAILED
        attempt = self.repo.add_attempt.call_args.args[0]
        assert attempt.result == AttemptResult.FAILED

    def test_propagates_invalid_transition_as_conflict(self):
        created = _charge(status=ChargeStatus.CAPTURED)  # ya estaba captured
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.side_effect = InvalidChargeTransitionError(
            ChargeStatus.CAPTURED, ChargeStatus.PENDING,
        )

        with pytest.raises(ConflictException) as exc:
            self.uc.execute(_request(), company_id=self.company_id, idempotency_key='k1')

        assert exc.value.code == AppErrorCode.PAY_INVALID_TRANSITION

    def test_stamps_active_period_id_from_lookup(self):
        from platform.features.billing.subscription.subscription.domain.schemas import ActivePeriodSchema
        period_id = uuid.uuid4()
        lookup = MagicMock()
        lookup.get.return_value = ActivePeriodSchema(
            id=period_id, subscription_id=uuid.uuid4(), status='active',
        )
        uc = CreateChargeUseCase(
            self.repo, self.router, period_lookup=lookup, currency_policy=self.policy,
        )
        created = _charge(company_id=self.company_id)
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result()
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        uc.execute(_request(), company_id=self.company_id)

        lookup.get.assert_called_once_with(self.company_id)
        schema = self.repo.create.call_args.args[0]
        assert schema.company_subscription_id == period_id

    def test_period_lookup_none_leaves_charge_unlinked(self):
        lookup = MagicMock()
        lookup.get.return_value = None
        uc = CreateChargeUseCase(
            self.repo, self.router, period_lookup=lookup, currency_policy=self.policy,
        )
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = _charge()
        self.gateway.create_charge.return_value = _result()
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        uc.execute(_request(), company_id=self.company_id)

        schema = self.repo.create.call_args.args[0]
        assert schema.company_subscription_id is None

    def test_period_lookup_failure_does_not_block_charge(self):
        lookup = MagicMock()
        lookup.get.side_effect = RuntimeError('lookup down')
        uc = CreateChargeUseCase(
            self.repo, self.router, period_lookup=lookup, currency_policy=self.policy,
        )
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = _charge()
        self.gateway.create_charge.return_value = _result()
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        uc.execute(_request(), company_id=self.company_id)

        schema = self.repo.create.call_args.args[0]
        assert schema.company_subscription_id is None

    @patch(
        'platform.features.billing.subscription.subscription.infrastructure.active_period.DjangoActivePeriodLookup',
    )
    def test_default_lookup_stamps_period_when_not_injected(self, MockLookup):
        from platform.features.billing.subscription.subscription.domain.schemas import ActivePeriodSchema
        period_id = uuid.uuid4()
        MockLookup.return_value.get.return_value = ActivePeriodSchema(
            id=period_id, subscription_id=uuid.uuid4(), status='active',
        )
        uc = CreateChargeUseCase(self.repo, self.router, currency_policy=self.policy)
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = _charge()
        self.gateway.create_charge.return_value = _result()
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        uc.execute(_request(), company_id=self.company_id)

        MockLookup.return_value.get.assert_called_once_with(self.company_id)
        schema = self.repo.create.call_args.args[0]
        assert schema.company_subscription_id == period_id

    def test_rejects_disallowed_currency_before_persist(self):
        self.policy = _currency_policy(allowed=('COP',))
        self.uc = CreateChargeUseCase(
            self.repo, self.router, currency_policy=self.policy,
        )
        with pytest.raises(ValidationAppException) as exc:
            self.uc.execute(_request(currency='EUR'), company_id=self.company_id)
        assert exc.value.code == AppErrorCode.PAY_CURRENCY_NOT_ALLOWED
        self.repo.create.assert_not_called()
        self.gateway.create_charge.assert_not_called()

    def test_normalizes_blank_currency_via_policy(self):
        created = _charge(company_id=self.company_id, currency='COP')
        self.repo.get_by_idempotency_key.return_value = None
        self.repo.create.return_value = created
        self.gateway.create_charge.return_value = _result(currency='COP')
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED, currency='COP')

        self.uc.execute(_request(currency=''), company_id=self.company_id)

        schema = self.repo.create.call_args.args[0]
        assert schema.currency == 'COP'


# ── ConfirmChargeUseCase ──────────────────────────────────────────────────────


class TestConfirmChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.uc = ConfirmChargeUseCase(self.repo, self.router)

    def test_confirms_charge_and_persists_new_status(self):
        existing = _charge(status=ChargeStatus.REQUIRES_ACTION)
        self.repo.get_by_id.return_value = existing
        self.gateway.confirm_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        result = self.uc.execute(existing.id, payload={'pin': '1234'})

        assert result.status == ChargeStatus.CAPTURED
        self.gateway.confirm_charge.assert_called_once_with(existing.gateway_charge_id, {'pin': '1234'})

    def test_raises_when_charge_does_not_exist(self):
        self.repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException) as exc:
            self.uc.execute(uuid.uuid4())
        assert exc.value.code == AppErrorCode.PAY_CHARGE_NOT_FOUND

    def test_records_failed_attempt_on_gateway_error(self):
        existing = _charge(status=ChargeStatus.REQUIRES_ACTION)
        self.repo.get_by_id.return_value = existing
        self.gateway.confirm_charge.side_effect = TimeoutError('boom')

        with pytest.raises(ServerException):
            self.uc.execute(existing.id)

        attempt = self.repo.add_attempt.call_args.args[0]
        assert attempt.operation == AttemptOperation.CONFIRM
        assert attempt.result == AttemptResult.FAILED


# ── CaptureChargeUseCase ──────────────────────────────────────────────────────


class TestCaptureChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.uc = CaptureChargeUseCase(self.repo, self.router)

    def test_captures_authorized_charge(self):
        existing = _charge(status=ChargeStatus.AUTHORIZED)
        self.repo.get_by_id.return_value = existing
        self.gateway.capture_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        result = self.uc.execute(existing.id, amount=Decimal('80'))

        assert result.status == ChargeStatus.CAPTURED
        self.gateway.capture_charge.assert_called_once_with(existing.gateway_charge_id, Decimal('80'))

    def test_capture_without_amount_passes_none(self):
        existing = _charge(status=ChargeStatus.AUTHORIZED)
        self.repo.get_by_id.return_value = existing
        self.gateway.capture_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        self.uc.execute(existing.id)

        self.gateway.capture_charge.assert_called_once_with(existing.gateway_charge_id, None)


# ── CancelChargeUseCase ───────────────────────────────────────────────────────


class TestCancelChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.uc = CancelChargeUseCase(self.repo, self.router)

    def test_cancels_charge_with_reason(self):
        existing = _charge(status=ChargeStatus.AUTHORIZED)
        self.repo.get_by_id.return_value = existing
        self.gateway.cancel_charge.return_value = _result(status=ChargeStatus.CANCELED)
        self.repo.transition.return_value = _charge(status=ChargeStatus.CANCELED)

        result = self.uc.execute(existing.id, reason='user changed mind')

        assert result.status == ChargeStatus.CANCELED
        self.gateway.cancel_charge.assert_called_once_with(existing.gateway_charge_id, 'user changed mind')

    def test_raises_when_charge_missing(self):
        self.repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            self.uc.execute(uuid.uuid4())


# ── RefundChargeUseCase ───────────────────────────────────────────────────────


class TestRefundChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.policy = _currency_policy()
        self.uc = RefundChargeUseCase(
            self.repo, self.router, currency_policy=self.policy,
        )

    def test_full_refund_transitions_to_refunded(self):
        existing = _charge(amount=Decimal('100'), refunded_amount=Decimal('0'),
                            status=ChargeStatus.CAPTURED)
        self.repo.get_by_id.return_value = existing
        self.gateway.refund_charge.return_value = RefundResult(
            gateway_provider=GatewayProvider.SIMULATOR,
            gateway_charge_id=existing.gateway_charge_id,
            gateway_refund_id='sim_rf_1',
            amount=Decimal('100'),
            status=ChargeStatus.REFUNDED,
        )
        self.repo.transition.return_value = _charge(status=ChargeStatus.REFUNDED,
                                                     refunded_amount=Decimal('100'))

        result = self.uc.execute(existing.id, reason='customer request')

        assert result.status == ChargeStatus.REFUNDED
        # La nueva refunded_amount se pasó al repo.
        update = self.repo.transition.call_args.args[1]
        assert update.refunded_amount == Decimal('100')

    def test_partial_refund_accumulates_refunded_amount(self):
        existing = _charge(amount=Decimal('200'), refunded_amount=Decimal('50'),
                            status=ChargeStatus.PARTIALLY_REFUNDED)
        self.repo.get_by_id.return_value = existing
        self.gateway.refund_charge.return_value = RefundResult(
            gateway_provider=GatewayProvider.SIMULATOR,
            gateway_charge_id=existing.gateway_charge_id,
            gateway_refund_id='sim_rf_2',
            amount=Decimal('30'),
            status=ChargeStatus.PARTIALLY_REFUNDED,
        )
        self.repo.transition.return_value = _charge(refunded_amount=Decimal('80'),
                                                     status=ChargeStatus.PARTIALLY_REFUNDED)

        self.uc.execute(existing.id, amount=Decimal('30'))

        update = self.repo.transition.call_args.args[1]
        # 50 (previo) + 30 (nuevo refund) = 80.
        assert update.refunded_amount == Decimal('80')

    def test_raises_when_charge_missing(self):
        self.repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            self.uc.execute(uuid.uuid4())

    def test_propagates_provider_error_as_server_exception(self):
        existing = _charge(status=ChargeStatus.CAPTURED)
        self.repo.get_by_id.return_value = existing
        self.gateway.refund_charge.side_effect = RuntimeError('gateway 500')

        with pytest.raises(ServerException):
            self.uc.execute(existing.id)

    def test_rejects_currency_mismatch(self):
        existing = _charge(status=ChargeStatus.CAPTURED, currency='COP')
        self.repo.get_by_id.return_value = existing
        with pytest.raises(ValidationAppException) as exc:
            self.uc.execute(existing.id, currency='USD')
        assert exc.value.code == AppErrorCode.PAY_CURRENCY_MISMATCH
        self.gateway.refund_charge.assert_not_called()


# ── FetchChargeUseCase ────────────────────────────────────────────────────────


class TestFetchChargeUseCase:

    def setup_method(self):
        self.repo = MagicMock()
        self.gateway = MagicMock()
        self.gateway.provider = GatewayProvider.SIMULATOR
        self.router = _router_returning(self.gateway)
        self.uc = FetchChargeUseCase(self.repo, self.router)

    def test_updates_state_when_provider_diverges(self):
        existing = _charge(status=ChargeStatus.PROCESSING)
        self.repo.get_by_id.return_value = existing
        self.gateway.fetch_charge.return_value = _result(status=ChargeStatus.CAPTURED)
        self.repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        result = self.uc.execute(existing.id)

        assert result.status == ChargeStatus.CAPTURED
        self.repo.transition.assert_called_once()

    def test_skips_transition_when_provider_agrees(self):
        existing = _charge(status=ChargeStatus.CAPTURED)
        self.repo.get_by_id.return_value = existing
        self.gateway.fetch_charge.return_value = _result(status=ChargeStatus.CAPTURED)

        result = self.uc.execute(existing.id)

        assert result is existing
        self.repo.transition.assert_not_called()

    def test_swallows_conflict_when_provider_reports_older_state(self):
        """Si el provider reporta un estado que la state machine no acepta,
        la reconciliación no debe romper — se queda con el estado local."""
        existing = _charge(status=ChargeStatus.REFUNDED)
        self.repo.get_by_id.return_value = existing
        self.gateway.fetch_charge.return_value = _result(status=ChargeStatus.PENDING)
        self.repo.transition.side_effect = InvalidChargeTransitionError(
            ChargeStatus.REFUNDED, ChargeStatus.PENDING,
        )

        result = self.uc.execute(existing.id)

        assert result is existing


# ── ProcessWebhookUseCase ─────────────────────────────────────────────────────


class TestProcessWebhookUseCase:

    def setup_method(self):
        self.charge_repo = MagicMock()
        self.inbox_repo = MagicMock()
        self.router = MagicMock()

    def _make_uc(self):
        return ProcessWebhookUseCase(self.charge_repo, self.inbox_repo, self.router)

    def _event(self, **overrides) -> WebhookEvent:
        defaults = dict(
            provider=GatewayProvider.SIMULATOR,
            external_event_id='evt_1',
            event_type=WebhookEventType.CHARGE_CAPTURED,
            gateway_charge_id='sim_ch_abc',
            status=ChargeStatus.CAPTURED,
            amount=Decimal('100'),
            currency='COP',
        )
        defaults.update(overrides)
        return WebhookEvent(**defaults)

    def _inbox_entry(self, **overrides) -> WebhookInboxEntrySchema:
        defaults = dict(
            id=uuid.uuid4(),
            provider='simulator',
            external_event_id='evt_1',
            event_type='charge.captured',
            payload={'id': 'evt_1', 'type': 'charge.captured', 'status': 'captured',
                     'charge_id': 'sim_ch_abc', 'amount': '100'},
            signature='sig',
            signature_verified=True,
        )
        defaults.update(overrides)
        return WebhookInboxEntrySchema(**defaults)

    def _patch_gateway(self, gateway):
        # _gateway_for_provider importa la factory dinámicamente
        # adentro del método. La parcheamos donde se usa.
        return patch(
            'platform.features.billing.commerce.payments.application.use_cases.ProcessWebhookUseCase._gateway_for_provider',
            return_value=gateway,
        )

    def test_processes_event_and_transitions_charge(self):
        entry = self._inbox_entry()
        existing = _charge(gateway_charge_id='sim_ch_abc', status=ChargeStatus.PROCESSING)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.parse_webhook_event.return_value = self._event(status=ChargeStatus.CAPTURED)
        self.charge_repo.get_by_gateway_ref.return_value = existing
        self.charge_repo.transition.return_value = _charge(status=ChargeStatus.CAPTURED)

        with self._patch_gateway(gateway):
            self._make_uc().execute(entry)

        self.charge_repo.transition.assert_called_once()
        self.inbox_repo.mark_processed.assert_called_once()
        kwargs = self.inbox_repo.mark_processed.call_args.kwargs
        assert kwargs.get('charge_id') == existing.id

    def test_rejects_unverified_signature(self):
        entry = self._inbox_entry(signature_verified=False)

        with pytest.raises(AppException) as exc:
            self._make_uc().execute(entry)

        assert exc.value.code == AppErrorCode.PAY_WEBHOOK_INVALID
        self.inbox_repo.mark_processed.assert_called_once()

    def test_skips_already_processed_event(self):
        from datetime import datetime, timezone as tz
        entry = self._inbox_entry(processed_at=datetime.now(tz.utc))
        result = self._make_uc().execute(entry)
        assert result is None
        self.charge_repo.get_by_gateway_ref.assert_not_called()

    def test_marks_processed_when_charge_not_found(self):
        entry = self._inbox_entry()
        gateway = MagicMock()
        gateway.parse_webhook_event.return_value = self._event()
        self.charge_repo.get_by_gateway_ref.return_value = None

        with self._patch_gateway(gateway):
            result = self._make_uc().execute(entry)

        assert result is None
        self.inbox_repo.mark_processed.assert_called_once()
        kwargs = self.inbox_repo.mark_processed.call_args.kwargs
        assert 'charge not found' in kwargs.get('error', '')

    def test_marks_processed_when_event_has_no_status(self):
        """Eventos informativos (sin transición) se cierran sin tocar la state machine."""
        entry = self._inbox_entry()
        existing = _charge(gateway_charge_id='sim_ch_abc')
        gateway = MagicMock()
        gateway.parse_webhook_event.return_value = self._event(status=None)
        self.charge_repo.get_by_gateway_ref.return_value = existing

        with self._patch_gateway(gateway):
            result = self._make_uc().execute(entry)

        assert result is existing
        self.charge_repo.transition.assert_not_called()
        self.inbox_repo.mark_processed.assert_called_once()

    def test_swallows_state_machine_rejection(self):
        """Webhook reordenado (estado ya superado) no debe romper el procesamiento."""
        entry = self._inbox_entry()
        existing = _charge(gateway_charge_id='sim_ch_abc', status=ChargeStatus.REFUNDED)
        gateway = MagicMock()
        gateway.provider = GatewayProvider.SIMULATOR
        gateway.parse_webhook_event.return_value = self._event(status=ChargeStatus.PENDING)
        self.charge_repo.get_by_gateway_ref.return_value = existing
        self.charge_repo.transition.side_effect = InvalidChargeTransitionError(
            ChargeStatus.REFUNDED, ChargeStatus.PENDING,
        )

        with self._patch_gateway(gateway):
            # Importante: el InvalidChargeTransitionError lo convierte _persist_state
            # en ConflictException, y el use case lo atrapa silenciosamente.
            result = self._make_uc().execute(entry)

        assert result is existing
        # Aun así marcamos como procesado, con un error en la nota.
        self.inbox_repo.mark_processed.assert_called_once()
        kwargs = self.inbox_repo.mark_processed.call_args.kwargs
        assert 'rejected' in kwargs.get('error', '').lower()

    def test_marks_processed_when_parse_fails(self):
        entry = self._inbox_entry()
        gateway = MagicMock()
        gateway.parse_webhook_event.side_effect = ValueError('malformed')

        with self._patch_gateway(gateway):
            with pytest.raises(AppException) as exc:
                self._make_uc().execute(entry)
            assert exc.value.code == AppErrorCode.PAY_WEBHOOK_INVALID

        self.inbox_repo.mark_processed.assert_called_once()
        kwargs = self.inbox_repo.mark_processed.call_args.kwargs
        assert 'parse error' in kwargs.get('error', '')
