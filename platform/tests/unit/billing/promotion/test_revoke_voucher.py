"""E4/E5 — RevokeVoucherUseCase."""

import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.use_cases import RevokeVoucherUseCase
from platform.tests.unit.billing.promotion.conftest import make_voucher_schema

pytestmark = pytest.mark.unit


class TestRevokeVoucherUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = RevokeVoucherUseCase(self.repo)

    def test_e4_revoke_active(self):
        revoked = make_voucher_schema(status='REVOKED')
        self.repo.revoke.return_value = revoked
        result = self.uc.execute(uuid.uuid4())
        self.assertEqual(result.status, 'REVOKED')

    def test_e5_redeemed_cannot_revoke(self):
        self.repo.revoke.side_effect = AppException(AppErrorCode.PROMO_INCOMPATIBLE)
        with self.assertRaises(AppException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INCOMPATIBLE)
