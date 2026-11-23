import uuid
from typing import Optional, List
from ..domain.interfaces import ISubscriptionRepository
from ..domain.schemas import (
    CompanySubscriptionResultSchema,
    CreateSubscriptionSchema,
    PendingChangeSchema,
    PendingDowngradeDueSchema,
    SubscriptionSchema,
    UpdateSubscriptionSchema,
)
from decimal import Decimal

from ..domain.billing_cycle import MONTHLY, charge_amount, normalize_billing_interval, period_delta
from ..models import Subscription, SubscriptionModule, SubscriptionFunctionality
from .billing_settings import live_annual_discount_percent, persist_annual_discount_percent


def _invalidate_access_cache(company_id) -> None:
    """Drop the company's cached plan/features so the live access checker
    reloads the new plan immediately after a change. Best-effort."""
    try:
        from core.access.subscription import SubscriptionCache
        SubscriptionCache.invalidate(str(company_id))
    except Exception:  # pragma: no cover - cache must never break a write
        pass


def _safe_interval(value) -> str:
    try:
        return normalize_billing_interval(value)
    except (TypeError, ValueError):
        return MONTHLY


def _acquisition_result(cs) -> CompanySubscriptionResultSchema:
    return CompanySubscriptionResultSchema(
        id=cs.id,
        subscription_id=cs.subscription.id,
        subscription_name=cs.subscription.name,
        start_date=cs.start_date,
        ends_at=cs.end_date,
        status=cs.status,
        billing_interval=_safe_interval(getattr(cs, 'billing_interval', None)),
    )


def _to_schema(s: Subscription, annual_discount_percent: Decimal | None = None) -> SubscriptionSchema:
    modules = list(
        SubscriptionModule.objects
        .filter(subscription=s)
        .values_list('module_code', flat=True)
    )
    features = list(
        SubscriptionFunctionality.objects
        .filter(subscription=s, functionality__is_active=True)
        .values_list('functionality__key', flat=True)
    )
    percent = (
        annual_discount_percent
        if annual_discount_percent is not None
        else live_annual_discount_percent()
    )
    return SubscriptionSchema(
        id=s.id,
        name=s.name,
        price=s.price,
        currency=getattr(s, 'currency', None) or 'USD',
        code=s.code,
        description=s.description,
        logo=s.logo,
        modules=modules,
        features=features,
        is_active=s.is_active,
        catalog_service_id=getattr(s, 'catalog_service_id', None),
        catalog_service_code=getattr(s, 'catalog_service_code', '') or '',
        catalog_service_name=getattr(s, 'catalog_service_name', '') or '',
        annual_discount_percent=percent,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


class DjangoSubscriptionRepository(ISubscriptionRepository):

    def get_all(self, filters: dict | None = None) -> List[SubscriptionSchema]:
        from django.db.models import Q

        qs = Subscription.objects.order_by('-price')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        percent = self.get_annual_discount_percent()
        from .neurana_catalog import overlay_catalog_prices
        return overlay_catalog_prices([_to_schema(s, percent) for s in qs])

    def get_active(self) -> List[SubscriptionSchema]:
        # Ascending by price so the wizard can render plans cheap-to-expensive
        # without an extra client-side sort.
        percent = self.get_annual_discount_percent()
        from .neurana_catalog import overlay_catalog_prices
        return overlay_catalog_prices([
            _to_schema(s, percent)
            for s in Subscription.objects.filter(is_active=True).order_by('price')
        ])

    def get_by_id(self, id: uuid.UUID) -> Optional[SubscriptionSchema]:
        try:
            obj = Subscription.objects.get(id=id)
        except Subscription.DoesNotExist:
            return None
        from .neurana_catalog import overlay_catalog_prices
        return overlay_catalog_prices([_to_schema(obj)])[0]

    def get_by_code(self, code: str) -> Optional[SubscriptionSchema]:
        try:
            obj = Subscription.objects.get(code=code)
        except Subscription.DoesNotExist:
            return None
        from .neurana_catalog import overlay_catalog_prices
        return overlay_catalog_prices([_to_schema(obj)])[0]

    def create(self, data: CreateSubscriptionSchema) -> SubscriptionSchema:
        obj = Subscription.objects.create(**data.model_dump())
        return _to_schema(obj)

    def update(self, id: uuid.UUID, data: UpdateSubscriptionSchema) -> Optional[SubscriptionSchema]:
        try:
            obj = Subscription.objects.get(id=id)
            before_active = obj.is_active
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, field, value)
            obj.save()
            if before_active != obj.is_active:
                from core.access.invalidation import invalidate_on_subscription_plan_change
                invalidate_on_subscription_plan_change(obj.id)
            return _to_schema(obj)
        except Subscription.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            Subscription.objects.get(id=id).delete()
            return True
        except Subscription.DoesNotExist:
            return False

    def activate_plan(
        self,
        company_id: uuid.UUID,
        subscription_id: uuid.UUID,
        *,
        billing_interval: str = MONTHLY,
        charge_id: Optional[uuid.UUID] = None,
    ):
        from django.utils import timezone
        from ..domain.events import PeriodClosed, PeriodIssued, publish
        from ..models import CompanySubscription
        try:
            subscription = Subscription.objects.get(id=subscription_id, is_active=True)
        except Subscription.DoesNotExist:
            return None
        interval = normalize_billing_interval(billing_interval)
        active_qs = CompanySubscription.objects.filter(
            company_id=company_id,
            status=CompanySubscription.Status.ACTIVE,
        )
        closed_ids = list(active_qs.values_list('id', flat=True))
        active_qs.update(status=CompanySubscription.Status.CLOSED)
        now = timezone.now()
        cs = CompanySubscription.objects.create(
            company_id=company_id,
            subscription=subscription,
            start_date=now,
            end_date=now + period_delta(interval),
            status=CompanySubscription.Status.ACTIVE,
            price_paid=charge_amount(
                subscription.price, interval, self.get_annual_discount_percent(),
            ),
            billing_interval=interval,
            pending_billing_interval=None,
        )
        _invalidate_access_cache(company_id)
        for closed_id in closed_ids:
            publish(PeriodClosed(company_id=company_id, period_id=closed_id))
        publish(PeriodIssued(
            company_id=company_id,
            period_id=cs.id,
            subscription_id=subscription.id,
            charge_id=charge_id,
            closed_period_ids=closed_ids,
        ))
        return _acquisition_result(cs)

    def cancel(self, company_id: uuid.UUID):
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if not cs:
            return None
        cs.status = CompanySubscription.Status.CANCELLED
        cs.save()
        _invalidate_access_cache(company_id)
        return _acquisition_result(cs)

    def reactivate(self, company_id: uuid.UUID):
        from django.utils import timezone
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.CANCELLED,
                end_date__gt=timezone.now(),
            )
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if not cs:
            return None
        cs.status = CompanySubscription.Status.ACTIVE
        cs.save()
        _invalidate_access_cache(company_id)
        return _acquisition_result(cs)

    def active_plan_id(self, company_id: uuid.UUID):
        from ..models import CompanySubscription
        return (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .order_by('-start_date')
            .values_list('subscription_id', flat=True)
            .first()
        )

    def get_active_acquisition(self, company_id: uuid.UUID):
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        return _acquisition_result(cs) if cs else None

    def active_billing_interval(self, company_id: uuid.UUID) -> str:
        from ..models import CompanySubscription
        interval = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .order_by('-start_date')
            .values_list('billing_interval', flat=True)
            .first()
        )
        return normalize_billing_interval(interval)

    def pending_billing_interval(self, company_id: uuid.UUID) -> str:
        """Interval to apply when the pending change materialises."""
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.ACTIVE,
                pending_subscription__isnull=False,
            )
            .order_by('-start_date')
            .only('pending_billing_interval', 'billing_interval')
            .first()
        )
        if cs is None:
            return MONTHLY
        return normalize_billing_interval(cs.pending_billing_interval or cs.billing_interval)

    def set_pending_downgrade(
        self, company_id: uuid.UUID, pending_subscription_id: uuid.UUID, *, billing_interval: str = None,
    ):
        """Record the pending (lower) plan on the active acquisition and return
        the CURRENT acquisition (unchanged — the company keeps it until vigencia)."""
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if not cs:
            return None
        cs.pending_subscription_id = pending_subscription_id
        pending_interval = (
            normalize_billing_interval(billing_interval)
            if billing_interval else (cs.billing_interval or MONTHLY)
        )
        cs.pending_billing_interval = pending_interval
        cs.save(update_fields=['pending_subscription', 'pending_billing_interval', 'updated_at'])
        return _acquisition_result(cs)

    def list_pending_downgrades_due(self) -> List[PendingDowngradeDueSchema]:
        from django.utils import timezone
        from ..models import CompanySubscription
        rows = (
            CompanySubscription.objects
            .filter(
                status=CompanySubscription.Status.ACTIVE,
                end_date__lte=timezone.now(),
                pending_subscription__isnull=False,
            )
            .values('company_id', 'pending_subscription_id')
        )
        return [
            PendingDowngradeDueSchema(
                company_id=r['company_id'],
                pending_subscription_id=r['pending_subscription_id'],
            )
            for r in rows
        ]

    def get_pending_change(self, company_id: uuid.UUID) -> Optional[PendingChangeSchema]:
        """The in-flight (not-yet-active) plan change for the company, or None.

        Only downgrades produce a pending change (the active acquisition keeps
        its plan until end_date). Returns the from/to plan names and the date
        it activates, for the settings UI + the single-change-at-a-time rule.
        """
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.ACTIVE,
                pending_subscription__isnull=False,
            )
            .select_related('subscription', 'pending_subscription')
            .order_by('-start_date')
            .first()
        )
        if cs is None:
            return None
        return PendingChangeSchema(
            type='downgrade',
            from_plan=cs.subscription.name,
            to_plan=cs.pending_subscription.name,
            activates_on=cs.end_date,
            billing_interval=normalize_billing_interval(
                cs.pending_billing_interval or cs.billing_interval,
            ),
        )

    def get_due_pending_downgrade(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        """The pending plan id IFF this company's active acquisition has
        expired with a pending downgrade — else None. Idempotency anchor: once
        the switch happens (old closed, new active without pending), this
        returns None so a second run is a no-op."""
        from django.utils import timezone
        from ..models import CompanySubscription
        return (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.ACTIVE,
                end_date__lte=timezone.now(),
                pending_subscription__isnull=False,
            )
            .values_list('pending_subscription_id', flat=True)
            .first()
        )

    # ── Renewal (same plan, recurring) ──────────────────────────────────────

    def get_renewal_due(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        """The active plan id IFF the company's active acquisition has expired,
        has NO pending downgrade, and auto_renew is on — i.e. it is due for a
        recurring renewal of the SAME plan. Else None (idempotency anchor)."""
        from django.utils import timezone
        from ..models import CompanySubscription
        return (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.ACTIVE,
                end_date__lte=timezone.now(),
                pending_subscription__isnull=True,
                auto_renew=True,
            )
            .values_list('subscription_id', flat=True)
            .first()
        )

    def list_renewals_due(self) -> List[uuid.UUID]:
        """Company ids whose active acquisition is due for renewal."""
        from django.utils import timezone
        from ..models import CompanySubscription
        return list(
            CompanySubscription.objects
            .filter(
                status=CompanySubscription.Status.ACTIVE,
                end_date__lte=timezone.now(),
                pending_subscription__isnull=True,
                auto_renew=True,
            )
            .values_list('company_id', flat=True)
        )

    def suspend(self, company_id: uuid.UUID):
        """Suspend the active acquisition (e.g. a renewal charge failed) and
        invalidate the access cache so its features are revoked at once."""
        from ..models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if not cs:
            return None
        cs.status = CompanySubscription.Status.SUSPENDED
        cs.save(update_fields=['status', 'updated_at'])
        _invalidate_access_cache(company_id)
        return _acquisition_result(cs)

    def get_suspended_acquisition(self, company_id: uuid.UUID, *, for_update: bool = False):
        from django.db import transaction
        from ..models import CompanySubscription

        qs = (
            CompanySubscription.objects
            .filter(
                company_id=company_id,
                status=CompanySubscription.Status.SUSPENDED,
            )
            .select_related('subscription')
            .order_by('-start_date')
        )
        if for_update:
            with transaction.atomic():
                cs = qs.select_for_update().first()
                return _acquisition_result(cs) if cs else None
        cs = qs.first()
        return _acquisition_result(cs) if cs else None

    def restore_after_payment(
        self,
        company_id: uuid.UUID,
        *,
        charge_id: Optional[uuid.UUID] = None,
    ):
        """Close the suspended period and open a new active billing cycle."""
        from django.db import transaction
        from ..models import CompanySubscription

        with transaction.atomic():
            cs = (
                CompanySubscription.objects
                .select_for_update()
                .filter(
                    company_id=company_id,
                    status=CompanySubscription.Status.SUSPENDED,
                )
                .select_related('subscription')
                .order_by('-start_date')
                .first()
            )
            if not cs:
                return None
            plan_id = cs.subscription_id
            interval = _safe_interval(cs.billing_interval)
            cs.status = CompanySubscription.Status.CLOSED
            cs.save(update_fields=['status', 'updated_at'])
            return self.activate_plan(
                company_id, plan_id, billing_interval=interval, charge_id=charge_id,
            )

    def expire_due(self, company_id: uuid.UUID | None = None) -> int:
        """Close out ACTIVE periods past vigencia with no pending change and
        auto_renew off. Returns the number of rows moved to ``expired``."""
        from django.utils import timezone
        from ..models import CompanySubscription
        qs = CompanySubscription.objects.filter(
            status=CompanySubscription.Status.ACTIVE,
            end_date__lte=timezone.now(),
            pending_subscription__isnull=True,
            auto_renew=False,
        )
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        company_ids = list(qs.values_list('company_id', flat=True))
        updated = qs.update(status=CompanySubscription.Status.EXPIRED)
        for cid in company_ids:
            _invalidate_access_cache(cid)
        return updated

    def get_annual_discount_percent(self) -> Decimal:
        return live_annual_discount_percent()

    def update_annual_discount_percent(self, percent: Decimal) -> Decimal:
        return persist_annual_discount_percent(percent)
