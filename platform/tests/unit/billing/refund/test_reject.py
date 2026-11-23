import uuid
from datetime import datetime, timezone as tz
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, ConflictException
from platform.features.billing.commerce.refund.application.reject import RejectRefundUseCase
from platform.features.billing.commerce.refund.domain.schemas import RefundTicketSchema

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_TICKET = uuid.uuid4()


def _ticket(**over):
    data = dict(
        id=_TICKET, ticket_number='RF-R', company_id=uuid.uuid4(), schema_name='acme',
        from_subscription_id=uuid.uuid4(), from_subscription_name='Pro',
        to_subscription_id=uuid.uuid4(), to_subscription_name='Free',
        period_id=uuid.uuid4(), charge_id=uuid.uuid4(), amount=Decimal('50'),
        currency='USD', kind='difference', status='pending',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )
    data.update(over)
    return RefundTicketSchema(**data)


def test_reject_pending_notifies_and_does_not_switch():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket()
    tickets.mark_rejected.return_value = _ticket(status='rejected', rejection_reason='Fuera de política')
    notifier = MagicMock()
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid.uuid4()]
    uc = RejectRefundUseCase(tickets, notifier, recipients)
    result = uc.execute(_TICKET, reason='Fuera de política')
    assert result.status == 'rejected'
    tickets.mark_rejected.assert_called_once()
    assert notifier.notify.call_args.args[0].status == 'rejected'


def test_reject_non_pending_conflicts():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket(status='processing')
    uc = RejectRefundUseCase(tickets, MagicMock(), MagicMock())
    with pytest.raises(ConflictException) as exc:
        uc.execute(_TICKET)
    assert exc.value.code == AppErrorCode.RFD_NOT_PENDING
