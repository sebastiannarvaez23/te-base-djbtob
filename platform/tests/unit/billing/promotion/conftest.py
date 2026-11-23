"""Shared helpers for promotion unit tests (no DB fixtures)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from platform.features.billing.commerce.promotion.domain.schemas import (
    ChargeSnapshot,
    CreateBulkVouchersSchema,
    CreateVoucherSchema,
    PlanSnapshot,
    RedeemResultSchema,
    RedemptionSchema,
    ValidateVoucherSchema,
    VoucherPreviewSchema,
    VoucherSchema,
)


def make_plan_snapshot(*, id=None, name='Pro', code='pro', price='100') -> PlanSnapshot:
    return PlanSnapshot(id=id or uuid.uuid4(), name=name, code=code, price=Decimal(str(price)))


class FakePlanCatalog:
    """In-memory ``IPlanCatalogPort`` for unit tests."""

    def __init__(
        self,
        target: PlanSnapshot,
        current: PlanSnapshot | None = None,
        billing_interval: str = 'monthly',
        annual_discount_percent: Decimal = Decimal('15'),
    ):
        self._target = target
        self._current = current
        self._billing_interval = billing_interval
        self._annual_discount_percent = annual_discount_percent
        self.activated: list = []

    def get_active_plan(self, subscription_id):
        return self._target

    def get_company_active_plan(self, company_id):
        return self._current

    def get_company_billing_interval(self, company_id):
        return self._billing_interval

    def get_annual_discount_percent(self):
        return self._annual_discount_percent

    def activate_plan(self, company_id, subscription_id, *, billing_interval='monthly'):
        self.activated.append((company_id, subscription_id, billing_interval))

    def list_all_company_ids(self):
        return []


class FakeChargePort:
    """In-memory ``IPromotionChargePort`` for unit tests."""

    def __init__(self, *, captured: bool = True, failure_message: str = '', exc: Exception | None = None):
        self._captured = captured
        self._failure_message = failure_message
        self._exc = exc
        self.calls: list = []

    def charge_plan(self, **kwargs) -> ChargeSnapshot:
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return ChargeSnapshot(
            id=uuid.uuid4(),
            status='CAPTURED' if self._captured else 'FAILED',
            failure_message=self._failure_message,
        )

    def bind_to_active_period(self, *, company_id, charge_id):
        self.calls.append({'bind_company_id': company_id, 'bind_charge_id': charge_id})


@pytest.fixture
def validity_window() -> dict:
    now = datetime(2026, 7, 1, 12, 0, 0)
    return {
        'redeem_valid_from': now,
        'redeem_valid_until': now + timedelta(days=30),
    }


def make_create_schema(
    *,
    voucher_type: str = 'GIFT',
    scope: str = 'OPEN',
    subscription_ids: list | None = None,
    benefit_months: int = 3,
    discount_percent: Decimal | None = None,
    company_id: uuid.UUID | None = None,
    **kwargs,
) -> CreateVoucherSchema:
    sub_id = subscription_ids or [uuid.uuid4()]
    now = datetime(2026, 7, 1, 12, 0, 0)
    base = dict(
        voucher_type=voucher_type,
        scope=scope,
        company_id=company_id,
        subscription_ids=sub_id,
        benefit_months=benefit_months if voucher_type == 'GIFT' else None,
        discount_percent=discount_percent if voucher_type == 'DISCOUNT' else None,
        discount_duration_months=1,
        redeem_valid_from=now,
        redeem_valid_until=now + timedelta(days=30),
        notes='test',
    )
    base.update(kwargs)
    return CreateVoucherSchema(**base)


def make_bulk_schema(**kwargs) -> CreateBulkVouchersSchema:
    now = datetime(2026, 7, 1, 12, 0, 0)
    base = dict(
        voucher_type='GIFT',
        scope='COMPANY',
        company_ids=[uuid.uuid4()],
        subscription_ids=[uuid.uuid4()],
        benefit_months=3,
        redeem_valid_from=now,
        redeem_valid_until=now + timedelta(days=30),
    )
    base.update(kwargs)
    return CreateBulkVouchersSchema(**base)


def make_voucher_schema(**overrides) -> VoucherSchema:
    now = datetime(2026, 7, 1, 12, 0, 0)
    defaults = dict(
        id=uuid.uuid4(),
        serial='WLGX-GFT-TEST0001',
        voucher_type='GIFT',
        scope='OPEN',
        origin='ADMIN',
        status='ACTIVE',
        company_id=None,
        company_name=None,
        discount_percent=None,
        benefit_months=3,
        discount_duration_months=1,
        redeem_valid_from=now,
        redeem_valid_until=now + timedelta(days=30),
        subscription_ids=[uuid.uuid4()],
        subscription_names=['Pro'],
        notes='',
        metadata={},
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return VoucherSchema(**defaults)


def make_preview(**overrides) -> VoucherPreviewSchema:
    now = datetime(2026, 7, 1, 12, 0, 0)
    defaults = dict(
        serial='WLGX-GFT-TEST0001',
        voucher_type='GIFT',
        subscription_id=uuid.uuid4(),
        subscription_name='Pro',
        original_amount=Decimal('100'),
        final_amount=Decimal('0'),
        discount_amount=Decimal('100'),
        benefit_months=3,
        discount_percent=None,
        discount_duration_months=1,
        redeem_valid_until=now + timedelta(days=30),
        message='ok',
    )
    defaults.update(overrides)
    return VoucherPreviewSchema(**defaults)


def make_redeem_result(**overrides) -> RedeemResultSchema:
    now = datetime(2026, 7, 1, 12, 0, 0)
    redemption_defaults = dict(
        id=uuid.uuid4(),
        voucher_id=uuid.uuid4(),
        voucher_serial='WLGX-GFT-TEST0001',
        company_id=uuid.uuid4(),
        company_name='Acme',
        redeemed_at=now,
        context='SETTINGS',
        subscription_id=uuid.uuid4(),
        subscription_name='Pro',
        original_amount=Decimal('100'),
        final_amount=Decimal('0'),
        discount_amount=Decimal('100'),
    )
    redemption_defaults.update(overrides.pop('redemption', {}))
    return RedeemResultSchema(
        redemption=RedemptionSchema(**redemption_defaults),
        preview=make_preview(**overrides.pop('preview', {})),
        benefit_id=overrides.pop('benefit_id', uuid.uuid4()),
        **overrides,
    )


def make_validate_schema(**overrides) -> ValidateVoucherSchema:
    defaults = dict(
        serial='WLGX-GFT-TEST0001',
        subscription_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        context='SETTINGS',
    )
    defaults.update(overrides)
    return ValidateVoucherSchema(**defaults)
