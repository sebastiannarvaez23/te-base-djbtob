"""E — Voucher expiry and revoke use cases."""

import uuid
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException, NotFoundException
from platform.features.billing.commerce.promotion.application.use_cases import (
    ExpireVouchersUseCase,
    RevokeVoucherUseCase,
)
from platform.tests.unit.billing.promotion.conftest import make_voucher_schema

pytestmark = pytest.mark.unit


class TestExpireVouchersUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = ExpireVouchersUseCase(self.repo)

    def test_e1_expires_active_past_due(self):
        self.repo.expire_due.return_value = 3
        now = datetime(2026, 8, 1, 0, 0, 0)
        count = self.uc.execute(now=now)
        self.repo.expire_due.assert_called_once_with(now=now)
        self.assertEqual(count, 3)


class TestRevokeVoucherUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = RevokeVoucherUseCase(self.repo)

    def test_e4_revoke_active(self):
        revoked = make_voucher_schema(status='REVOKED')
        self.repo.revoke.return_value = revoked
        result = self.uc.execute(uuid.uuid4())
        self.assertEqual(result.status, 'REVOKED')

    def test_e5_revoke_redeemed_raises(self):
        self.repo.revoke.side_effect = AppException(AppErrorCode.PROMO_INCOMPATIBLE)
        with self.assertRaises(AppException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INCOMPATIBLE)

    def test_revoke_not_found(self):
        self.repo.revoke.side_effect = NotFoundException(AppErrorCode.PROMO_NOT_FOUND)
        with self.assertRaises(NotFoundException):
            self.uc.execute(uuid.uuid4())
