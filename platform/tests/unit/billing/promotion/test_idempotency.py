"""F — Idempotency on redeem (repository short-circuit via port)."""

import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from platform.features.billing.commerce.promotion.application.use_cases import RedeemVoucherUseCase
from platform.features.billing.commerce.promotion.domain.schemas import RedeemVoucherSchema
from platform.tests.unit.billing.promotion.conftest import (
    FakeChargePort,
    FakePlanCatalog,
    make_plan_snapshot,
    make_redeem_result,
)

pytestmark = pytest.mark.unit


class TestRedeemIdempotency(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = RedeemVoucherUseCase(
            self.repo, FakePlanCatalog(make_plan_snapshot()), FakeChargePort(),
        )

    def test_f1_same_idempotency_key_returns_existing(self):
        expected = make_redeem_result()
        self.repo.find_redemption_by_idempotency.return_value = expected

        data = RedeemVoucherSchema(
            serial='WLGX-GFT-TEST0001',
            subscription_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            context='ONBOARDING',
            idempotency_key='idem-abc-123',
        )
        r1 = self.uc.execute(data)
        r2 = self.uc.execute(data)

        self.assertEqual(r1.redemption.id, r2.redemption.id)
        self.repo.get_by_serial.assert_not_called()
        self.repo.persist_redeem.assert_not_called()
