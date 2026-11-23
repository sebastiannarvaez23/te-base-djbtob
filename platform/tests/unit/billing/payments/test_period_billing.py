"""Unit tests for binding a charge/invoice to a CompanySubscription period."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.invoice.application.bind_period import BindInvoiceToPeriodUseCase
from platform.features.billing.commerce.payments.application.bind_period import BindChargeToPeriodUseCase
from platform.features.billing.commerce.payments.domain.schemas import ChargeSchema
from platform.features.billing.commerce.payments.integration.period_issued import PeriodIssuedChargeListener
from platform.features.billing.commerce.invoice.integration.period_issued import PeriodIssuedInvoiceListener
from platform.features.billing.subscription.subscription.domain.events import PeriodIssued

pytestmark = pytest.mark.unit


def test_bind_charge_updates_via_repository():
    charge_id = uuid.uuid4()
    period_id = uuid.uuid4()
    repo = MagicMock()
    updated = MagicMock(spec=ChargeSchema)
    repo.bind_period.return_value = updated

    result = BindChargeToPeriodUseCase(repo).execute(charge_id, period_id)

    repo.bind_period.assert_called_once_with(charge_id, period_id)
    assert result is updated


def test_bind_charge_raises_when_missing():
    repo = MagicMock()
    repo.bind_period.return_value = None
    with pytest.raises(AppException) as exc:
        BindChargeToPeriodUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())
    assert exc.value.code == AppErrorCode.SUB_PERIOD_BIND_FAILED


def test_bind_invoice_uses_source_charge():
    charge_id = uuid.uuid4()
    period_id = uuid.uuid4()
    repo = MagicMock()
    repo.bind_period_for_source_charge.return_value = 1

    updated = BindInvoiceToPeriodUseCase(repo).execute(charge_id, period_id)

    repo.bind_period_for_source_charge.assert_called_once_with(charge_id, period_id)
    assert updated == 1


def test_bind_invoice_returns_zero_when_nothing_matches():
    repo = MagicMock()
    repo.bind_period_for_source_charge.return_value = 0
    assert BindInvoiceToPeriodUseCase(repo).execute(uuid.uuid4(), uuid.uuid4()) == 0


def test_period_issued_charge_listener_skips_without_charge():
    repo = MagicMock()
    listener = PeriodIssuedChargeListener(charge_repo_factory=lambda: repo)
    listener.on_period_issued(PeriodIssued(
        company_id=uuid.uuid4(),
        period_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        charge_id=None,
    ))
    repo.bind_period.assert_not_called()


def test_period_issued_invoice_listener_skips_without_charge():
    repo = MagicMock()
    listener = PeriodIssuedInvoiceListener(invoice_repo_factory=lambda: repo)
    listener.on_period_issued(PeriodIssued(
        company_id=uuid.uuid4(),
        period_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        charge_id=None,
    ))
    repo.bind_period_for_source_charge.assert_not_called()


def test_period_issued_listeners_bind_when_charge_present():
    charge_id = uuid.uuid4()
    period_id = uuid.uuid4()
    charge_repo = MagicMock()
    invoice_repo = MagicMock()
    charge_repo.bind_period.return_value = MagicMock(spec=ChargeSchema)
    invoice_repo.bind_period_for_source_charge.return_value = 1
    event = PeriodIssued(
        company_id=uuid.uuid4(),
        period_id=period_id,
        subscription_id=uuid.uuid4(),
        charge_id=charge_id,
    )
    PeriodIssuedChargeListener(charge_repo_factory=lambda: charge_repo).on_period_issued(event)
    PeriodIssuedInvoiceListener(invoice_repo_factory=lambda: invoice_repo).on_period_issued(event)
    charge_repo.bind_period.assert_called_once_with(charge_id, period_id)
    invoice_repo.bind_period_for_source_charge.assert_called_once_with(charge_id, period_id)


def test_charge_listener_propagates_bind_failure():
    repo = MagicMock()
    repo.bind_period.return_value = None
    listener = PeriodIssuedChargeListener(charge_repo_factory=lambda: repo)
    with pytest.raises(AppException) as exc:
        listener.on_period_issued(PeriodIssued(
            company_id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            subscription_id=uuid.uuid4(),
            charge_id=uuid.uuid4(),
        ))
    assert exc.value.code == AppErrorCode.SUB_PERIOD_BIND_FAILED


@patch('platform.features.billing.commerce.payments.infrastructure.repositories.Charge')
def test_charge_repo_bind_period_updates_by_pk(MockCharge):
    from platform.features.billing.commerce.payments.infrastructure.repositories import (
        DjangoChargeRepository,
    )
    charge_id, period_id = uuid.uuid4(), uuid.uuid4()
    MockCharge.objects.filter.return_value.update.return_value = 1
    expected = MagicMock(spec=ChargeSchema)
    repo = DjangoChargeRepository()
    with patch.object(repo, 'get_by_id', return_value=expected) as get:
        result = repo.bind_period(charge_id, period_id)
    MockCharge.objects.filter.assert_called_with(id=charge_id)
    MockCharge.objects.filter.return_value.update.assert_called_with(
        company_subscription_id=period_id,
    )
    get.assert_called_once_with(charge_id)
    assert result is expected


@patch('platform.features.billing.commerce.payments.infrastructure.repositories.Charge')
def test_charge_repo_bind_period_returns_none_when_missing(MockCharge):
    from platform.features.billing.commerce.payments.infrastructure.repositories import (
        DjangoChargeRepository,
    )
    MockCharge.objects.filter.return_value.update.return_value = 0
    assert DjangoChargeRepository().bind_period(uuid.uuid4(), uuid.uuid4()) is None


@patch('platform.features.billing.commerce.invoice.infrastructure.repositories.Invoice')
def test_invoice_repo_bind_period_updates_by_pk(MockInvoice):
    from platform.features.billing.commerce.invoice.infrastructure.repositories import (
        DjangoInvoiceRepository,
    )
    invoice_id, period_id = uuid.uuid4(), uuid.uuid4()
    MockInvoice.objects.filter.return_value.update.return_value = 1
    n = DjangoInvoiceRepository().bind_period(invoice_id, period_id)
    MockInvoice.objects.filter.assert_called_once_with(id=invoice_id)
    MockInvoice.objects.filter.return_value.update.assert_called_once_with(
        company_subscription_id=period_id,
    )
    assert n == 1


@patch('platform.features.billing.commerce.invoice.infrastructure.repositories.Invoice')
def test_invoice_repo_bind_uses_source_charge_column(MockInvoice):
    from platform.features.billing.commerce.invoice.infrastructure.repositories import (
        DjangoInvoiceRepository,
    )
    charge_id, period_id = uuid.uuid4(), uuid.uuid4()
    qs = MagicMock()
    qs.update.return_value = 1
    MockInvoice.objects.filter.return_value = qs
    n = DjangoInvoiceRepository().bind_period_for_source_charge(charge_id, period_id)
    MockInvoice.objects.filter.assert_called_once_with(source_charge_id=charge_id)
    qs.update.assert_called_once_with(company_subscription_id=period_id)
    assert n == 1


@patch('platform.features.billing.commerce.invoice.infrastructure.repositories.Invoice')
def test_invoice_repo_bind_falls_back_to_metadata(MockInvoice):
    from platform.features.billing.commerce.invoice.infrastructure.repositories import (
        DjangoInvoiceRepository,
    )
    charge_id, period_id = uuid.uuid4(), uuid.uuid4()

    def filter_side_effect(*args, **kwargs):
        qs = MagicMock()
        qs.update.return_value = 0 if 'source_charge_id' in kwargs else 1
        return qs

    MockInvoice.objects.filter.side_effect = filter_side_effect
    n = DjangoInvoiceRepository().bind_period_for_source_charge(charge_id, period_id)
    assert n == 1
    MockInvoice.objects.filter.assert_any_call(source_charge_id=charge_id)
    MockInvoice.objects.filter.assert_any_call(metadata__source_charge_id=str(charge_id))


@patch('platform.features.billing.commerce.invoice.infrastructure.repositories.Invoice')
def test_invoice_repo_bind_returns_zero_when_neither_match(MockInvoice):
    from platform.features.billing.commerce.invoice.infrastructure.repositories import (
        DjangoInvoiceRepository,
    )
    qs = MagicMock()
    qs.update.return_value = 0
    MockInvoice.objects.filter.return_value = qs
    n = DjangoInvoiceRepository().bind_period_for_source_charge(
        uuid.uuid4(), uuid.uuid4(),
    )
    assert n == 0
    assert MockInvoice.objects.filter.call_count == 2
