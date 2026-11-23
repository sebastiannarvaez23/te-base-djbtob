import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as tz
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.refund.application.create import CreateRefundRequestUseCase
from platform.features.billing.commerce.refund.domain.schemas import (
    PeriodSnapshot,
    RefundPreviewSchema,
    RefundEligibilitySchema,
    RefundTicketSchema,
    RefundableCharge,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_COMPANY = uuid.uuid4()
_PLAN = uuid.uuid4()
_TARGET = uuid.uuid4()
_PERIOD = uuid.uuid4()
_CHARGE = uuid.uuid4()
_TICKET = uuid.uuid4()


@contextmanager
def _atomic():
    yield


def _frozen_now():
    return _NOW


def _period():
    return PeriodSnapshot(
        id=_PERIOD, company_id=_COMPANY, subscription_id=_PLAN,
        subscription_name='Pro', start_date=_NOW - timedelta(hours=1),
        price_paid=Decimal('100'), billing_interval='monthly', status='active',
    )


def _charge():
    return RefundableCharge(
        id=_CHARGE, amount=Decimal('100'), refunded_amount=Decimal('0'),
        currency='USD', status='captured',
    )


def _preview():
    return RefundPreviewSchema(
        eligibility=RefundEligibilitySchema(eligible=True),
        target_plan_id=_TARGET, target_plan_name='Free',
        target_amount=Decimal('0'), refund_amount=Decimal('100'),
        refund_kind='full', currency='USD', payout_due_on=_NOW.date(),
    )


def _ticket():
    return RefundTicketSchema(
        id=_TICKET, ticket_number='RF-TEST', company_id=_COMPANY,
        schema_name='acme', from_subscription_id=_PLAN, from_subscription_name='Pro',
        to_subscription_id=_TARGET, to_subscription_name='Free',
        period_id=_PERIOD, charge_id=_CHARGE, amount=Decimal('100'),
        currency='USD', kind='full', status='pending',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_submit_opens_pending_ticket_without_switch_or_payout():
    evaluate = MagicMock()
    evaluate.preview.return_value = _preview()
    tickets = MagicMock()
    tickets.get_open.return_value = None
    tickets.last_accepted_at.return_value = None
    tickets.create.return_value = _ticket()
    periods = MagicMock()
    periods.get_active.return_value = _period()
    charges = MagicMock()
    charges.get_for_period.return_value = _charge()
    notifier = MagicMock()
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid.uuid4()]

    uc = CreateRefundRequestUseCase(
        evaluate, tickets, periods, charges, notifier, recipients,
    )
    result = uc.execute(_COMPANY, _TARGET, 'acme', requested_by_id=uuid.uuid4())

    assert result.status == 'pending'
    tickets.create.assert_called_once()
    notifier.notify.assert_called_once()
    note = notifier.notify.call_args.args[0]
    assert note.status == 'pending'
    assert 'revisión' in note.body


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_open_ticket_race_does_not_create_side_effects():
    from django.db import IntegrityError
    from core.errors import ConflictException

    evaluate = MagicMock()
    evaluate.preview.return_value = _preview()
    tickets = MagicMock()
    tickets.get_open.return_value = None
    tickets.last_accepted_at.return_value = None
    tickets.create.side_effect = IntegrityError()
    periods = MagicMock()
    periods.get_active.return_value = _period()
    charges = MagicMock()
    charges.get_for_period.return_value = _charge()
    notifier = MagicMock()
    uc = CreateRefundRequestUseCase(
        evaluate, tickets, periods, charges, notifier, MagicMock(),
    )
    with pytest.raises(ConflictException):
        uc.execute(_COMPANY, _TARGET, 'acme')
    notifier.notify.assert_not_called()
