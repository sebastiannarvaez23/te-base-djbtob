import uuid
from contextlib import contextmanager
from datetime import datetime, timezone as tz
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException
from platform.features.billing.commerce.refund.application.approve import ApproveRefundUseCase
from platform.features.billing.commerce.refund.domain.schemas import (
    PeriodSnapshot,
    RefundTicketSchema,
    RefundableCharge,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_COMPANY = uuid.uuid4()
_TICKET = uuid.uuid4()
_TARGET = uuid.uuid4()
_PERIOD = uuid.uuid4()
_CHARGE = uuid.uuid4()
_ADMIN = uuid.uuid4()


@contextmanager
def _atomic():
    yield


def _immediate(fn):
    fn()


def _ticket(**over):
    data = dict(
        id=_TICKET, ticket_number='RF-A', company_id=_COMPANY, schema_name='acme',
        from_subscription_id=uuid.uuid4(), from_subscription_name='Pro',
        to_subscription_id=_TARGET, to_subscription_name='Free',
        period_id=_PERIOD, charge_id=_CHARGE, amount=Decimal('100'),
        currency='USD', kind='full', status='pending',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )
    data.update(over)
    return RefundTicketSchema(**data)


@patch('platform.features.billing.commerce.refund.application.approve.transaction.atomic', _atomic)
@patch('platform.features.billing.commerce.refund.application.approve.transaction.on_commit', _immediate)
def test_approve_switches_plan_enqueues_and_notifies():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket()
    tickets.mark_approved.return_value = _ticket(status='accepted')
    periods = MagicMock()
    periods.get_active.return_value = PeriodSnapshot(
        id=_PERIOD, company_id=_COMPANY, subscription_id=uuid.uuid4(),
        subscription_name='Pro', start_date=_NOW, price_paid=Decimal('100'),
        billing_interval='monthly', status='active',
    )
    charges = MagicMock()
    charges.get_for_period.return_value = RefundableCharge(
        id=_CHARGE, amount=Decimal('100'), refunded_amount=Decimal('0'),
        currency='USD', status='captured',
    )
    company_periods = MagicMock()
    company_periods.activate_plan.return_value = MagicMock()
    notifier = MagicMock()
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid.uuid4()]
    enqueue = MagicMock()
    kill_sessions = MagicMock()

    uc = ApproveRefundUseCase(
        tickets, periods, charges, company_periods, notifier, recipients,
        enqueue, kill_sessions,
    )
    result = uc.execute(_TICKET, approved_by_id=_ADMIN)

    assert result.status == 'accepted'
    tickets.mark_approved.assert_called_once()
    company_periods.activate_plan.assert_called_once_with(
        _COMPANY, _TARGET, billing_interval='monthly',
    )
    enqueue.assert_called_once_with(_TICKET)
    kill_sessions.assert_called_once_with(_COMPANY)
    assert notifier.notify.call_args.args[0].status == 'accepted'


@patch('platform.features.billing.commerce.refund.application.approve.transaction.atomic', _atomic)
def test_approve_rejects_non_pending():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket(status='accepted')
    uc = ApproveRefundUseCase(
        tickets, MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )
    with pytest.raises(ConflictException) as exc:
        uc.execute(_TICKET)
    assert exc.value.code == AppErrorCode.RFD_NOT_PENDING


def test_approve_missing_ticket():
    tickets = MagicMock()
    tickets.get_by_id.return_value = None
    uc = ApproveRefundUseCase(
        tickets, MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )
    with pytest.raises(NotFoundException):
        uc.execute(_TICKET)


@patch('platform.features.billing.commerce.refund.application.approve.transaction.atomic', _atomic)
@patch('platform.features.billing.commerce.refund.application.approve.transaction.on_commit', _immediate)
def test_approve_still_succeeds_if_session_kill_fails():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket()
    tickets.mark_approved.return_value = _ticket(status='accepted')
    periods = MagicMock()
    periods.get_active.return_value = PeriodSnapshot(
        id=_PERIOD, company_id=_COMPANY, subscription_id=uuid.uuid4(),
        subscription_name='Pro', start_date=_NOW, price_paid=Decimal('100'),
        billing_interval='monthly', status='active',
    )
    charges = MagicMock()
    charges.get_for_period.return_value = RefundableCharge(
        id=_CHARGE, amount=Decimal('100'), refunded_amount=Decimal('0'),
        currency='USD', status='captured',
    )
    company_periods = MagicMock()
    company_periods.activate_plan.return_value = MagicMock()
    kill_sessions = MagicMock(side_effect=RuntimeError('redis down'))

    uc = ApproveRefundUseCase(
        tickets, periods, charges, company_periods, MagicMock(), MagicMock(),
        MagicMock(), kill_sessions,
    )
    result = uc.execute(_TICKET, approved_by_id=_ADMIN)

    assert result.status == 'accepted'
    kill_sessions.assert_called_once_with(_COMPANY)
