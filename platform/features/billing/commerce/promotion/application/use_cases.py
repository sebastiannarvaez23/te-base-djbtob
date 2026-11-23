"""Promotion use cases.

Orchestration only: use cases depend on the repository port, cross-feature
ports (plan catalog, charge) and pure domain services. They never import Django
models nor instantiate concrete adapters (that is ``composition.py``'s job).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from core.errors import AppErrorCode, AppException, NotFoundException

from ..domain.interfaces import (
    IPlanCatalogPort,
    IPromotionChargePort,
    IPromotionVoucherRepository,
)
from ..domain.schemas import (
    ActiveBenefitSchema,
    BulkCreateResultSchema,
    CreateBenefitSchema,
    CreateBulkVouchersSchema,
    CreateRedemptionSchema,
    CreateVoucherSchema,
    PlanSnapshot,
    RedeemResultSchema,
    RedeemVoucherSchema,
    RedemptionSchema,
    ValidateVoucherSchema,
    VoucherPreviewSchema,
    VoucherSchema,
)
from ..domain.services.benefit_window import build_benefit_window
from ..domain.services.create_rules import validate_create_input
from ..domain.services.eligibility import (
    assert_plan_eligible,
    assert_redeemable,
    assert_scope,
)
from ..domain.services.plan_effect import decide_plan_effect
from ..domain.services.preview import compute_preview
from core.trace import trace_layer


def validate_and_price(
    repo: IPromotionVoucherRepository,
    plan_catalog: IPlanCatalogPort,
    *,
    serial: str,
    subscription_id: uuid.UUID,
    company_id: Optional[uuid.UUID],
    context: str,
    check_active_benefit: bool = True,
    billing_interval: Optional[str] = None,
) -> tuple[VoucherSchema, PlanSnapshot, Optional[PlanSnapshot], Decimal, Decimal, Decimal, str]:
    """Shared validate → price pipeline for validate/redeem (pure rules + ports)."""
    voucher = repo.get_by_serial(serial)
    if voucher is None:
        raise NotFoundException(AppErrorCode.PROMO_NOT_FOUND)

    assert_redeemable(
        status=voucher.status,
        valid_from=voucher.redeem_valid_from,
        valid_until=voucher.redeem_valid_until,
        now=datetime.now(timezone.utc),
    )
    assert_scope(scope=voucher.scope, voucher_company_id=voucher.company_id, company_id=company_id)

    if company_id is not None and check_active_benefit and context == 'SETTINGS':
        if repo.has_active_benefit(company_id):
            from core.errors import ConflictException

            raise ConflictException(AppErrorCode.PROMO_BENEFIT_ACTIVE)

    target = plan_catalog.get_active_plan(subscription_id)
    current = plan_catalog.get_company_active_plan(company_id) if company_id else None
    assert_plan_eligible(allowed_plan_ids=voucher.subscription_ids, target=target, current=current)

    interval = billing_interval
    if not interval and company_id is not None:
        interval = plan_catalog.get_company_billing_interval(company_id)
    annual_pct = plan_catalog.get_annual_discount_percent()
    original, final, discount, message = compute_preview(
        voucher_type=voucher.voucher_type,
        benefit_months=voucher.benefit_months,
        discount_percent=voucher.discount_percent,
        discount_duration_months=voucher.discount_duration_months,
        target=target,
        billing_interval=interval or 'monthly',
        annual_discount_percent=annual_pct,
    )
    return voucher, target, current, original, final, discount, message


def _preview_schema(
    voucher: VoucherSchema,
    target: PlanSnapshot,
    original: Decimal,
    final: Decimal,
    discount: Decimal,
    message: str,
) -> VoucherPreviewSchema:
    return VoucherPreviewSchema(
        serial=voucher.serial,
        voucher_type=voucher.voucher_type,
        subscription_id=target.id,
        subscription_name=target.name,
        original_amount=original,
        final_amount=final,
        discount_amount=discount,
        benefit_months=voucher.benefit_months,
        discount_percent=voucher.discount_percent,
        discount_duration_months=voucher.discount_duration_months,
        redeem_valid_until=voucher.redeem_valid_until,
        message=message,
    )


class CreateVoucherUseCase:
    def __init__(self, repository: IPromotionVoucherRepository, *, notifier=None):
        self._repo = repository
        self._notifier = notifier

    @trace_layer('application')
    def execute(self, data: CreateVoucherSchema) -> VoucherSchema:
        validate_create_input(data)
        voucher = self._repo.create(data)
        if self._notifier is not None:
            self._notifier(voucher)
        return voucher


class CreateBulkVouchersUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, data: CreateBulkVouchersSchema) -> BulkCreateResultSchema:
        # Validate shared voucher fields once before persistence.
        probe = CreateVoucherSchema(
            voucher_type=data.voucher_type,
            scope='COMPANY',
            company_id=uuid.uuid4(),
            subscription_ids=data.subscription_ids,
            discount_percent=data.discount_percent,
            benefit_months=data.benefit_months,
            discount_duration_months=data.discount_duration_months,
            redeem_valid_from=data.redeem_valid_from,
            redeem_valid_until=data.redeem_valid_until,
            notes=data.notes,
            created_by_id=data.created_by_id,
        )
        validate_create_input(probe)
        return self._repo.create_bulk(data)


class ListVouchersUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, **filters):
        return self._repo.list_vouchers(**filters)


class GetVoucherUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, voucher_id: uuid.UUID) -> VoucherSchema:
        result = self._repo.get_by_id(voucher_id)
        if result is None:
            raise NotFoundException(AppErrorCode.PROMO_NOT_FOUND)
        return result


class ListRedemptionsUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, **filters) -> list[RedemptionSchema]:
        return self._repo.list_redemptions(**filters)


class ValidateVoucherUseCase:
    def __init__(self, repository: IPromotionVoucherRepository, plan_catalog: IPlanCatalogPort):
        self._repo = repository
        self._plan_catalog = plan_catalog

    @trace_layer('application')
    def execute(self, data: ValidateVoucherSchema) -> VoucherPreviewSchema:
        voucher, target, current, original, final, discount, message = validate_and_price(
            self._repo,
            self._plan_catalog,
            serial=data.serial,
            subscription_id=data.subscription_id,
            company_id=data.company_id,
            context=data.context,
            billing_interval=data.billing_interval,
        )
        return _preview_schema(voucher, target, original, final, discount, message)


class RedeemVoucherUseCase:
    def __init__(
        self,
        repository: IPromotionVoucherRepository,
        plan_catalog: IPlanCatalogPort,
        charge_port: Optional[IPromotionChargePort] = None,
    ):
        self._repo = repository
        self._plan_catalog = plan_catalog
        self._charge_port = charge_port

    @trace_layer('application')
    def execute(self, data: RedeemVoucherSchema) -> RedeemResultSchema:
        if data.idempotency_key:
            existing = self._repo.find_redemption_by_idempotency(data.idempotency_key)
            if existing is not None:
                return existing

        voucher, target, current, original, final, discount, message = validate_and_price(
            self._repo,
            self._plan_catalog,
            serial=data.serial,
            subscription_id=data.subscription_id,
            company_id=data.company_id,
            context=data.context,
            billing_interval=data.billing_interval,
        )

        needs_charge = data.context == 'SETTINGS' and final is not None and final > 0
        if needs_charge and not data.payment_method_id:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail='A payment method is required to redeem a paid voucher.',
            )

        activate_plan_id, previous_plan_id = decide_plan_effect(
            voucher_type=voucher.voucher_type, target=target, current=current,
        )

        if voucher.voucher_type == 'GIFT':
            months = voucher.benefit_months or 1
            discount_percent = None
            remaining_cycles = None
        else:
            months = voucher.discount_duration_months or 1
            discount_percent = voucher.discount_percent
            remaining_cycles = voucher.discount_duration_months

        start, end = build_benefit_window(months=months, start=datetime.now(timezone.utc))

        redemption = CreateRedemptionSchema(
            voucher_id=voucher.id,
            company_id=data.company_id,
            context=data.context,
            subscription_id=target.id,
            original_amount=original,
            final_amount=final,
            discount_amount=discount,
            idempotency_key=data.idempotency_key,
        )
        benefit = CreateBenefitSchema(
            company_id=data.company_id,
            voucher_type=voucher.voucher_type,
            subscription_id=target.id,
            previous_subscription_id=previous_plan_id,
            benefit_start=start,
            benefit_end=end,
            discount_percent=discount_percent,
            remaining_discount_cycles=remaining_cycles,
        )

        result = self._repo.persist_redeem(
            voucher_id=voucher.id,
            redemption=redemption,
            benefit=benefit,
            activate_plan_id=activate_plan_id,
        )
        result.preview.message = message

        if not needs_charge:
            return result

        try:
            self._charge(data.company_id, data.payment_method_id, result)
        except Exception:
            self._repo.rollback_redeem(
                company_id=data.company_id,
                voucher_serial=result.preview.serial,
                benefit_id=result.benefit_id,
                redemption_id=result.redemption.id,
                previous_plan_id=result.previous_plan_id,
                attempted_plan_id=result.preview.subscription_id,
            )
            raise
        return result

    def _charge(self, company_id, payment_method_id, result: RedeemResultSchema) -> None:
        if self._charge_port is None:
            raise AppException(AppErrorCode.PROMO_INTERNAL)
        preview = result.preview
        original_amount = Decimal(str(preview.original_amount))
        discount_amount = Decimal(str(preview.discount_amount))
        final_amount = Decimal(str(preview.final_amount))
        promo_email = {
            'promotion_serial': preview.serial,
            'promotion_voucher_type': preview.voucher_type,
            'promotion_original_amount': float(original_amount),
            'promotion_discount_amount': float(discount_amount),
        }
        charge = self._charge_port.charge_plan(
            company_id=company_id,
            amount=final_amount,
            payment_method_id=payment_method_id,
            metadata={
                'promotion_redemption_id': str(result.redemption.id),
                'promotion_serial': preview.serial,
                'voucher_type': preview.voucher_type,
                'original_amount': str(original_amount),
                'discount_amount': str(discount_amount),
                'email_context': promo_email,
            },
            description=f'Redención bono — {preview.subscription_name}',
        )
        if not charge.is_captured:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail=(
                    charge.failure_message
                    or 'El pago no pudo procesarse; no se aplicó el bono.'
                ),
            )


class ListActiveBenefitsUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID, *, status: str | None = None) -> list[ActiveBenefitSchema]:
        return self._repo.list_active_benefits(company_id, status=status)


class RevokeVoucherUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, voucher_id: uuid.UUID) -> VoucherSchema:
        return self._repo.revoke(voucher_id)


class ExpireVouchersUseCase:
    def __init__(self, repository: IPromotionVoucherRepository):
        self._repo = repository

    @trace_layer('application')
    def execute(self, *, now=None) -> int:
        now = now or datetime.now(timezone.utc)
        return self._repo.expire_due(now=now)
