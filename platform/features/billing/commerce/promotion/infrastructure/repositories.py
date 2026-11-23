"""Django persistence adapter for promotion vouchers.

Persistence + mapping ONLY. No imports from the application layer, no email
sending, no redeem/validate business orchestration — those live in the domain
services and application use cases. This adapter turns already-decided inputs
(schemas) into rows and rows back into schemas.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException

from platform.features.billing.commerce.promotion.domain.interfaces import IPromotionVoucherRepository
from platform.features.billing.commerce.promotion.domain.schemas import (
    ActiveBenefitSchema,
    BulkCreateResultSchema,
    CreateBenefitSchema,
    CreateBulkVouchersSchema,
    CreateRedemptionSchema,
    CreateVoucherSchema,
    RedeemResultSchema,
    RedemptionSchema,
    VoucherPreviewSchema,
    VoucherSchema,
)
from platform.features.billing.commerce.promotion.domain.services.serial import generate_voucher_serial
from platform.features.billing.commerce.promotion.models import (
    PromotionBenefit,
    PromotionRedemption,
    PromotionVoucher,
)
from platform.features.company.tenant.company.models import Company


def _to_voucher_schema(v: PromotionVoucher) -> VoucherSchema:
    subs = list(v.subscriptions.all())
    return VoucherSchema(
        id=v.id,
        serial=v.serial,
        voucher_type=v.voucher_type,
        scope=v.scope,
        origin=v.origin,
        status=v.status,
        company_id=v.company_id,
        company_name=getattr(v.company, 'name', None) if v.company_id else None,
        discount_percent=v.discount_percent,
        benefit_months=v.benefit_months,
        discount_duration_months=v.discount_duration_months,
        redeem_valid_from=v.redeem_valid_from,
        redeem_valid_until=v.redeem_valid_until,
        subscription_ids=[s.id for s in subs],
        subscription_names=[s.name for s in subs],
        subscription_prices=[s.price for s in subs],
        notes=v.notes or '',
        metadata=v.metadata or {},
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


def _to_redemption_schema(r: PromotionRedemption) -> RedemptionSchema:
    return RedemptionSchema(
        id=r.id,
        voucher_id=r.voucher_id,
        voucher_serial=r.voucher.serial,
        company_id=r.company_id,
        company_name=r.company.name,
        redeemed_at=r.redeemed_at,
        context=r.context,
        subscription_id=r.subscription_id,
        subscription_name=r.subscription.name,
        original_amount=r.original_amount,
        final_amount=r.final_amount,
        discount_amount=r.discount_amount,
    )


def _to_active_benefit_schema(b: PromotionBenefit) -> ActiveBenefitSchema:
    voucher = getattr(getattr(b, 'redemption', None), 'voucher', None)
    benefit_months = getattr(voucher, 'benefit_months', None) if voucher else None
    if not benefit_months and b.voucher_type == PromotionVoucher.VoucherType.GIFT:
        benefit_months = _months_between(b.benefit_start, b.benefit_end)
    return ActiveBenefitSchema(
        id=b.id,
        voucher_type=b.voucher_type,
        voucher_serial=getattr(voucher, 'serial', '') or '',
        voucher_id=getattr(voucher, 'id', None) if voucher else None,
        subscription_id=b.subscription_id,
        subscription_name=getattr(b.subscription, 'name', '') or '',
        benefit_start=b.benefit_start,
        benefit_end=b.benefit_end,
        benefit_months=benefit_months,
        discount_percent=b.discount_percent,
        remaining_discount_cycles=b.remaining_discount_cycles,
        discount_duration_months=getattr(voucher, 'discount_duration_months', None) if voucher else None,
        status=b.status,
        company_id=getattr(b, 'company_id', None),
        previous_subscription_id=getattr(b, 'previous_subscription_id', None),
    )


def _as_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value


def _months_between(start, end) -> int | None:
    start_dt = _as_datetime(start)
    end_dt = _as_datetime(end)
    if not start_dt or not end_dt:
        return None
    try:
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(end_dt, start_dt)
        months = delta.years * 12 + delta.months
        if delta.days >= 15:
            months += 1
        return max(1, months) if end_dt > start_dt else None
    except Exception:
        return None


def _preview_from_redemption(r: PromotionRedemption) -> VoucherPreviewSchema:
    return VoucherPreviewSchema(
        serial=r.voucher.serial,
        voucher_type=r.voucher.voucher_type,
        subscription_id=r.subscription_id,
        subscription_name=r.subscription.name,
        original_amount=r.original_amount,
        final_amount=r.final_amount,
        discount_amount=r.discount_amount,
        benefit_months=r.voucher.benefit_months,
        discount_percent=r.voucher.discount_percent,
        discount_duration_months=r.voucher.discount_duration_months,
        redeem_valid_until=r.voucher.redeem_valid_until,
        message='',
    )


class DjangoPromotionVoucherRepository(IPromotionVoucherRepository):

    # ── serials ──────────────────────────────────────────────────────────────

    def next_serial(self, voucher_type: str) -> str:
        prefix = getattr(settings, 'PROMO_SERIAL_PREFIX', 'WLGX')
        for _ in range(10):
            serial = generate_voucher_serial(voucher_type, prefix=prefix)
            if not PromotionVoucher.objects.filter(serial__iexact=serial).exists():
                return serial
        raise AppException(AppErrorCode.PROMO_INTERNAL)

    # ── vouchers ──────────────────────────────────────────────────────────────

    def create(self, data: CreateVoucherSchema, *, serial: str | None = None) -> VoucherSchema:
        # Business create rules are validated in CreateVoucherUseCase.
        serial = serial or self.next_serial(data.voucher_type)
        with transaction.atomic():
            voucher = PromotionVoucher.objects.create(
                serial=serial,
                voucher_type=data.voucher_type,
                scope=data.scope,
                origin=PromotionVoucher.Origin.ADMIN,
                status=PromotionVoucher.Status.ACTIVE,
                company_id=data.company_id,
                discount_percent=data.discount_percent,
                benefit_months=data.benefit_months,
                discount_duration_months=data.discount_duration_months,
                redeem_valid_from=data.redeem_valid_from,
                redeem_valid_until=data.redeem_valid_until,
                notes=data.notes,
                created_by_id=data.created_by_id,
            )
            voucher.subscriptions.set(data.subscription_ids)
        return _to_voucher_schema(
            PromotionVoucher.objects.prefetch_related('subscriptions').select_related('company').get(id=voucher.id)
        )

    def create_bulk(self, data: CreateBulkVouchersSchema) -> BulkCreateResultSchema:
        company_ids = list(data.company_ids)
        if data.all_companies:
            company_ids = list(Company.objects.values_list('id', flat=True))
        if not company_ids:
            raise AppException(AppErrorCode.PROMO_INVALID_INPUT)

        created = []
        failed = []
        for cid in company_ids:
            try:
                item = CreateVoucherSchema(
                    voucher_type=data.voucher_type,
                    scope='COMPANY',
                    company_id=cid,
                    subscription_ids=data.subscription_ids,
                    discount_percent=data.discount_percent,
                    benefit_months=data.benefit_months,
                    discount_duration_months=data.discount_duration_months,
                    redeem_valid_from=data.redeem_valid_from,
                    redeem_valid_until=data.redeem_valid_until,
                    notes=data.notes,
                    created_by_id=data.created_by_id,
                )
                created.append(self.create(item))
            except Exception as exc:
                failed.append({'company_id': str(cid), 'error': str(exc)})

        return BulkCreateResultSchema(created=len(created), failed=failed, vouchers=created)

    def get_by_id(self, voucher_id: uuid.UUID) -> VoucherSchema | None:
        try:
            v = PromotionVoucher.objects.prefetch_related('subscriptions').select_related('company').get(id=voucher_id)
            return _to_voucher_schema(v)
        except PromotionVoucher.DoesNotExist:
            return None

    def get_by_serial(self, serial: str) -> VoucherSchema | None:
        v = (
            PromotionVoucher.objects
            .filter(serial__iexact=serial.strip())
            .prefetch_related('subscriptions')
            .select_related('company')
            .first()
        )
        return _to_voucher_schema(v) if v else None

    def list_vouchers(self, **filters):
        from django.db.models import Q
        from math import ceil

        from core.query import PaginatedResult

        page = int(filters.pop('page', 0) or 0)
        page_size = int(filters.pop('page_size', 20) or 20)
        page = max(0, page)
        page_size = max(1, min(page_size, 100))

        qs = PromotionVoucher.objects.prefetch_related('subscriptions').select_related('company')
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('voucher_type'):
            qs = qs.filter(voucher_type=filters['voucher_type'])
        if filters.get('scope'):
            qs = qs.filter(scope=filters['scope'])
        if filters.get('origin'):
            qs = qs.filter(origin=filters['origin'])
        if filters.get('company_id'):
            qs = qs.filter(company_id=filters['company_id'])
        if filters.get('serial'):
            qs = qs.filter(serial__icontains=filters['serial'])
        if filters.get('company'):
            qs = qs.filter(company__name__icontains=filters['company'])
        search = (filters.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(serial__icontains=search)
                | Q(company__name__icontains=search)
                | Q(subscriptions__name__icontains=search)
            ).distinct()

        qs = qs.order_by('-created_at')
        total = qs.count()
        start = page * page_size
        items = [_to_voucher_schema(v) for v in qs[start:start + page_size]]
        total_pages = max(1, ceil(total / page_size)) if total else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def list_redemptions(self, **filters) -> list[RedemptionSchema]:
        qs = PromotionRedemption.objects.select_related('voucher', 'company', 'subscription')
        if filters.get('company_id'):
            qs = qs.filter(company_id=filters['company_id'])
        if filters.get('voucher_id'):
            qs = qs.filter(voucher_id=filters['voucher_id'])
        return [_to_redemption_schema(r) for r in qs.order_by('-redeemed_at')]

    def revoke(self, voucher_id: uuid.UUID) -> VoucherSchema:
        try:
            v = PromotionVoucher.objects.get(id=voucher_id)
        except PromotionVoucher.DoesNotExist:
            raise NotFoundException(AppErrorCode.PROMO_NOT_FOUND)
        if v.status != PromotionVoucher.Status.ACTIVE:
            raise AppException(AppErrorCode.PROMO_INCOMPATIBLE)
        v.status = PromotionVoucher.Status.REVOKED
        v.save(update_fields=['status', 'updated_at'])
        return _to_voucher_schema(
            PromotionVoucher.objects.prefetch_related('subscriptions').select_related('company').get(id=v.id)
        )

    def expire_due(self, *, now: datetime) -> int:
        return (
            PromotionVoucher.objects
            .filter(status=PromotionVoucher.Status.ACTIVE, redeem_valid_until__lt=now)
            .update(status=PromotionVoucher.Status.EXPIRED)
        )

    # ── benefits ──────────────────────────────────────────────────────────────

    def has_active_benefit(self, company_id: uuid.UUID) -> bool:
        return PromotionBenefit.objects.filter(
            company_id=company_id,
            status=PromotionBenefit.Status.ACTIVE,
        ).exists()

    def get_active_benefit(self, company_id, *, subscription_id=None):
        qs = (
            PromotionBenefit.objects.filter(
                company_id=company_id,
                status=PromotionBenefit.Status.ACTIVE,
            )
            .select_related('subscription', 'previous_subscription', 'redemption__voucher')
        )
        if subscription_id is not None:
            qs = qs.filter(subscription_id=subscription_id)
        benefit = qs.first()
        return _to_active_benefit_schema(benefit) if benefit else None

    def list_active_benefits(
        self,
        company_id: uuid.UUID,
        *,
        status: str | None = None,
    ) -> list[ActiveBenefitSchema]:
        benefit_status = status or PromotionBenefit.Status.ACTIVE
        benefits = (
            PromotionBenefit.objects.filter(
                company_id=company_id,
                status=benefit_status,
            )
            .select_related('subscription', 'redemption__voucher')
            .order_by('-benefit_start')
        )
        return [_to_active_benefit_schema(b) for b in benefits]

    def list_gift_benefits_due_for_revert(self, *, now: datetime) -> list[ActiveBenefitSchema]:
        benefits = (
            PromotionBenefit.objects.filter(
                status=PromotionBenefit.Status.ACTIVE,
                voucher_type=PromotionVoucher.VoucherType.GIFT,
                previous_subscription_id__isnull=False,
                benefit_end__lte=now,
            ).select_related('company', 'previous_subscription', 'subscription', 'redemption__voucher')
        )
        return [_to_active_benefit_schema(b) for b in benefits]

    def create_benefit(self, data: CreateBenefitSchema) -> ActiveBenefitSchema:
        benefit = PromotionBenefit.objects.create(
            company_id=data.company_id,
            redemption_id=data.redemption_id,
            voucher_type=data.voucher_type,
            subscription_id=data.subscription_id,
            previous_subscription_id=data.previous_subscription_id,
            benefit_start=data.benefit_start,
            benefit_end=data.benefit_end,
            discount_percent=data.discount_percent,
            remaining_discount_cycles=data.remaining_discount_cycles,
            status=PromotionBenefit.Status.ACTIVE,
        )
        return _to_active_benefit_schema(
            PromotionBenefit.objects.select_related('subscription', 'redemption__voucher').get(id=benefit.id)
        )

    def complete_benefit(self, benefit_id: uuid.UUID) -> None:
        PromotionBenefit.objects.filter(id=benefit_id).update(
            status=PromotionBenefit.Status.COMPLETED,
        )

    def cancel_benefits(self, company_id, *, voucher_types=None) -> int:
        qs = PromotionBenefit.objects.filter(
            company_id=company_id,
            status=PromotionBenefit.Status.ACTIVE,
        )
        if voucher_types:
            qs = qs.filter(voucher_type__in=voucher_types)
        count = qs.count()
        if count:
            qs.update(status=PromotionBenefit.Status.CANCELLED)
        return count

    def decrement_discount_cycle(self, benefit_id: uuid.UUID) -> None:
        with transaction.atomic():
            benefit = (
                PromotionBenefit.objects
                .select_for_update()
                .get(id=benefit_id)
            )
            if benefit.remaining_discount_cycles is None:
                return
            remaining = benefit.remaining_discount_cycles - 1
            if remaining <= 0:
                benefit.remaining_discount_cycles = 0
                benefit.status = PromotionBenefit.Status.COMPLETED
            else:
                benefit.remaining_discount_cycles = remaining
            benefit.save(update_fields=['remaining_discount_cycles', 'status', 'updated_at'])

    # ── redemption unit of work ────────────────────────────────────────────────

    def find_redemption_by_idempotency(self, key: str) -> RedeemResultSchema | None:
        existing = (
            PromotionRedemption.objects.filter(idempotency_key=key)
            .select_related('voucher', 'company', 'subscription')
            .first()
        )
        if existing is None:
            return None
        benefit = PromotionBenefit.objects.filter(redemption_id=existing.id).first()
        return RedeemResultSchema(
            redemption=_to_redemption_schema(existing),
            preview=_preview_from_redemption(existing),
            benefit_id=benefit.id if benefit else None,
            previous_plan_id=(benefit.previous_subscription_id if benefit else None),
        )

    def persist_redeem(
        self,
        *,
        voucher_id: uuid.UUID,
        redemption: CreateRedemptionSchema,
        benefit: CreateBenefitSchema,
        activate_plan_id=None,
    ) -> RedeemResultSchema:
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )

        with transaction.atomic():
            locked = PromotionVoucher.objects.select_for_update().get(id=voucher_id)
            if locked.status != PromotionVoucher.Status.ACTIVE:
                raise AppException(AppErrorCode.PROMO_NOT_ACTIVE)

            if activate_plan_id is not None:
                interval = DjangoSubscriptionRepository().active_billing_interval(redemption.company_id)
                DjangoSubscriptionRepository().activate_plan(
                    redemption.company_id, activate_plan_id, billing_interval=interval,
                )

            now = timezone.now()
            redemption_row = PromotionRedemption.objects.create(
                voucher=locked,
                company_id=redemption.company_id,
                redeemed_at=now,
                context=redemption.context,
                subscription_id=redemption.subscription_id,
                original_amount=redemption.original_amount,
                final_amount=redemption.final_amount,
                discount_amount=redemption.discount_amount,
                idempotency_key=redemption.idempotency_key,
            )
            locked.status = PromotionVoucher.Status.REDEEMED
            locked.save(update_fields=['status', 'updated_at'])

            benefit_row = PromotionBenefit.objects.create(
                company_id=benefit.company_id,
                redemption=redemption_row,
                voucher_type=benefit.voucher_type,
                subscription_id=benefit.subscription_id,
                previous_subscription_id=benefit.previous_subscription_id,
                benefit_start=benefit.benefit_start,
                benefit_end=benefit.benefit_end,
                discount_percent=benefit.discount_percent,
                remaining_discount_cycles=benefit.remaining_discount_cycles,
                status=PromotionBenefit.Status.ACTIVE,
            )

        redemption_full = PromotionRedemption.objects.select_related(
            'voucher', 'company', 'subscription',
        ).get(id=redemption_row.id)
        preview = _preview_from_redemption(redemption_full)
        return RedeemResultSchema(
            redemption=_to_redemption_schema(redemption_full),
            preview=preview,
            benefit_id=benefit_row.id,
            previous_plan_id=benefit_row.previous_subscription_id,
        )

    def rollback_redeem(
        self,
        *,
        company_id,
        voucher_serial,
        benefit_id,
        redemption_id,
        previous_plan_id,
        attempted_plan_id,
    ) -> None:
        """Compensate a SETTINGS redeem when the charge fails after commit."""
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )

        with transaction.atomic():
            if benefit_id:
                PromotionBenefit.objects.filter(id=benefit_id).update(
                    status=PromotionBenefit.Status.CANCELLED,
                )
            if redemption_id:
                PromotionRedemption.objects.filter(id=redemption_id).delete()
            PromotionVoucher.objects.filter(serial=voucher_serial).update(
                status=PromotionVoucher.Status.ACTIVE,
            )
            if previous_plan_id is not None and previous_plan_id != attempted_plan_id:
                DjangoSubscriptionRepository().activate_plan(company_id, previous_plan_id)

    # ── public purchase persistence ────────────────────────────────────────────

    def find_by_checkout_idempotency(self, idempotency_key: str) -> VoucherSchema | None:
        by_column = PromotionVoucher.objects.filter(
            checkout_idempotency_key=idempotency_key,
        ).prefetch_related('subscriptions').select_related('company').first()
        if by_column is not None:
            return _to_voucher_schema(by_column)
        legacy = PromotionVoucher.objects.filter(
            metadata__checkout_idempotency_key=idempotency_key,
        ).prefetch_related('subscriptions').select_related('company').first()
        return _to_voucher_schema(legacy) if legacy else None

    def create_public_purchase_voucher(
        self,
        *,
        voucher_type: str,
        subscription_id: uuid.UUID,
        benefit_months: int | None,
        discount_percent: Decimal | None,
        discount_duration_months: int,
        redeem_valid_from: datetime,
        redeem_valid_until: datetime,
        metadata: dict,
        recipient_message: str = '',
        checkout_idempotency_key: str | None = None,
    ) -> VoucherSchema:
        serial = self.next_serial(voucher_type)
        notes = recipient_message[:500] if recipient_message else ''
        key = checkout_idempotency_key or metadata.get('checkout_idempotency_key')
        try:
            with transaction.atomic():
                voucher = PromotionVoucher.objects.create(
                    serial=serial,
                    voucher_type=voucher_type,
                    scope=PromotionVoucher.Scope.OPEN,
                    origin=PromotionVoucher.Origin.PUBLIC_PURCHASE,
                    status=PromotionVoucher.Status.ACTIVE,
                    company_id=None,
                    discount_percent=discount_percent,
                    benefit_months=benefit_months,
                    discount_duration_months=discount_duration_months,
                    redeem_valid_from=redeem_valid_from,
                    redeem_valid_until=redeem_valid_until,
                    notes=notes,
                    metadata=metadata,
                    checkout_idempotency_key=key,
                )
                voucher.subscriptions.set([subscription_id])
        except IntegrityError as exc:
            # A concurrent checkout won the unique-idempotency race; surface a
            # domain conflict so the application layer can re-fetch and return
            # the winning voucher instead of leaking a Django exception.
            raise ConflictException(AppErrorCode.PROMO_IDEMPOTENCY_HIT) from exc
        return _to_voucher_schema(
            PromotionVoucher.objects.prefetch_related('subscriptions').select_related('company').get(id=voucher.id)
        )
