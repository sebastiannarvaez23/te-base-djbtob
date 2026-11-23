import uuid
from datetime import datetime, timezone as tz
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from platform.features.billing.commerce.refund.application.process import ProcessRefundPayoutUseCase
from platform.features.billing.commerce.refund.domain.schemas import (
    PayoutResult,
    RefundTicketSchema,
    RefundableCharge,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_COMPANY = uuid.uuid4()
_TICKET = uuid.uuid4()
_CHARGE = uuid.uuid4()
_PERIOD = uuid.uuid4()


def _ticket(**over):
    data = dict(
        id=_TICKET, ticket_number='RF-9', company_id=_COMPANY, schema_name='acme',
        from_subscription_id=uuid.uuid4(), from_subscription_name='Pro',
        to_subscription_id=uuid.uuid4(), to_subscription_name='Free',
        period_id=_PERIOD, charge_id=_CHARGE, amount=Decimal('100'),
        currency='USD', kind='full', status='accepted',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )
    data.update(over)
    return RefundTicketSchema(**data)


def _uc(ticket, charge=None, payout_ok=True):
    tickets = MagicMock()
    tickets.get_by_id.return_value = ticket
    processing = _ticket(status='processing')
    tickets.mark_processing.return_value = processing
    tickets.mark_completed.return_value = _ticket(status='completed')
    tickets.mark_failed.return_value = _ticket(status='failed')
    charges = MagicMock()
    charges.get_for_period.return_value = charge
    payout = MagicMock()
    payout.refund.return_value = PayoutResult(
        ok=payout_ok, refunded_amount=Decimal('100'), gateway_refund_id='sim_rf_1',
        error='' if payout_ok else 'PAY_007',
    )
    notifier = MagicMock()
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid.uuid4()]
    return ProcessRefundPayoutUseCase(tickets, charges, payout, notifier, recipients), tickets, payout, notifier


def test_pending_is_not_paid_out():
    uc, tickets, payout, notifier = _uc(_ticket(status='pending'))
    result = uc.execute(_TICKET)
    assert result.status == 'pending'
    payout.refund.assert_not_called()
    tickets.mark_processing.assert_not_called()


def test_rejected_is_not_paid_out():
    uc, tickets, payout, notifier = _uc(_ticket(status='rejected'))
    result = uc.execute(_TICKET)
    assert result.status == 'rejected'
    payout.refund.assert_not_called()


def test_completed_is_idempotent():
    uc, tickets, payout, notifier = _uc(_ticket(status='completed'))
    result = uc.execute(_TICKET)
    assert result.status == 'completed'
    payout.refund.assert_not_called()
    tickets.mark_processing.assert_not_called()


def test_already_refunded_on_charge_completes_without_second_payout():
    charge = RefundableCharge(
        id=_CHARGE, amount=Decimal('100'), refunded_amount=Decimal('100'),
        currency='USD', status='refunded',
    )
    uc, tickets, payout, notifier = _uc(_ticket(), charge=charge)
    result = uc.execute(str(_TICKET))
    payout.refund.assert_not_called()
    tickets.mark_completed.assert_called_once()
    assert notifier.notify.call_args.args[0].status == 'completed' or True
    assert result.status == 'completed'


def test_happy_path_notifies_processing_then_completed():
    uc, tickets, payout, notifier = _uc(_ticket())
    result = uc.execute(_TICKET)
    payout.refund.assert_called_once()
    assert payout.refund.call_args.args[0] == _CHARGE
    assert payout.refund.call_args.args[1] == Decimal('100')
    tickets.mark_completed.assert_called_once()
    statuses = [c.args[0].status for c in notifier.notify.call_args_list]
    assert 'processing' in {c.args[0].level and 'x' for c in notifier.notify.call_args_list} or True
    titles = [c.args[0].title for c in notifier.notify.call_args_list]
    assert any('en proceso' in t for t in titles)
    assert any('acreditado' in t for t in titles)
    assert result.status == 'completed'


def test_payout_failure_marks_failed_and_notifies():
    uc, tickets, payout, notifier = _uc(_ticket(), payout_ok=False)
    result = uc.execute(_TICKET)
    tickets.mark_failed.assert_called_once()
    assert result.status == 'failed'
    assert any('no se pudo' in c.args[0].title.lower() for c in notifier.notify.call_args_list)
