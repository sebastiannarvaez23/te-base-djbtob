from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from core.errors import AppException, AppErrorCode
from platform.features.billing.commerce.refund.infrastructure.payout import ChargeGatewayRefundAdapter
from platform.features.billing.commerce.refund.domain.schemas import PayoutResult

pytestmark = pytest.mark.unit


def test_adapter_maps_success():
    charge_uc = MagicMock()
    charge_uc.execute.return_value = MagicMock(
        refunded_amount=Decimal('40'), gateway_charge_id='sim_ch_1',
    )
    result = ChargeGatewayRefundAdapter(charge_uc).refund(
        MagicMock(), Decimal('40'), 'refund RF-1',
    )
    assert isinstance(result, PayoutResult)
    assert result.ok is True
    assert result.refunded_amount == Decimal('40')
    charge_uc.execute.assert_called_once()


def test_adapter_maps_app_exception():
    charge_uc = MagicMock()
    charge_uc.execute.side_effect = AppException(AppErrorCode.PAY_PROVIDER_ERROR)
    result = ChargeGatewayRefundAdapter(charge_uc).refund(
        MagicMock(), Decimal('10'), 'x',
    )
    assert result.ok is False
    assert result.error == 'PAY_007'
