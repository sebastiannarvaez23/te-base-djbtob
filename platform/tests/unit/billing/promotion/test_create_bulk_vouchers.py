"""A.2 — CreateBulkVouchersUseCase unit tests."""

import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.use_cases import CreateBulkVouchersUseCase
from platform.features.billing.commerce.promotion.domain.schemas import BulkCreateResultSchema
from platform.tests.unit.billing.promotion.conftest import make_bulk_schema, make_voucher_schema

pytestmark = pytest.mark.unit


class TestCreateBulkVouchersUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateBulkVouchersUseCase(self.repo)

    def test_a2_1_two_companies(self):
        v1 = make_voucher_schema(serial='WLGX-GFT-AAA11111')
        v2 = make_voucher_schema(serial='WLGX-GFT-BBB22222')
        self.repo.create_bulk.return_value = BulkCreateResultSchema(
            created=2, failed=[], vouchers=[v1, v2],
        )
        result = self.uc.execute(make_bulk_schema(
            company_ids=[uuid.uuid4(), uuid.uuid4()],
        ))
        self.assertEqual(result.created, 2)
        self.assertEqual(len(result.vouchers), 2)
        self.assertNotEqual(result.vouchers[0].serial, result.vouchers[1].serial)

    def test_a2_4_empty_list_raises(self):
        self.repo.create_bulk.side_effect = AppException(AppErrorCode.PROMO_INVALID_INPUT)
        with self.assertRaises(AppException) as ctx:
            self.uc.execute(make_bulk_schema(company_ids=[]))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a2_5_partial_failure_in_summary(self):
        self.repo.create_bulk.return_value = BulkCreateResultSchema(
            created=1,
            failed=[{'company_id': str(uuid.uuid4()), 'error': 'not found'}],
            vouchers=[make_voucher_schema()],
        )
        result = self.uc.execute(make_bulk_schema())
        self.assertEqual(result.created, 1)
        self.assertEqual(len(result.failed), 1)
