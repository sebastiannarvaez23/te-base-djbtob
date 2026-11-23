"""Garbage-collect tenants whose admin user never confirmed their email.

Background — by design ``finalize`` provisions the tenant (Company +
schema + admin User) and dispatches the email-confirmation link
afterwards. Login is gated by ``AUTH_007`` until the link is clicked,
but the tenant rows still live in the database. Users who walk away
mid-confirmation leave behind a row in ``companies`` and a Postgres
schema that nobody will ever use.

This sweep targets exactly that case:

  * The Company has at least one User and **every** User on it has
    ``email_verified_at IS NULL`` (not a single member ever logged in
    successfully).
  * The Company was created more than ``retention_days`` days ago
    (``Company.created`` — DateField, only meaningfully advances when
    Company is saved, which never happens for an abandoned tenant).

For each match the sweep:

  * Skips the company if it already has settled billing (captured /
    refunded charges or a paid invoice) — those rows are financial
    evidence and must not be garbage-collected.
  * Otherwise deletes public-schema billing children that use
    ``DO_NOTHING`` (charges, invoices, promotion vouchers / redemptions)
    so ``Company.delete`` is not blocked by FKs.
  * Deletes User rows (FK is PROTECT) and then
    ``company.delete(force_drop=True)`` so django-tenants drops the
    schema. CASCADE on Domain.tenant handles domain rows.

Idempotent: a second invocation with the same ``retention_days`` returns
``(0, 0)`` because all candidates are gone after the first one.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from core.trace import trace_layer


logger = logging.getLogger('app.api')

# Charge.Status values that mean money actually moved. Kept as strings so this
# module does not import billing models at load time.
_SETTLED_CHARGE_STATUSES = (
    'captured',
    'refunded',
    'partially_refunded',
    'disputed',
)


def _has_settled_billing(company) -> bool:
    """True when dropping the tenant would erase a real payment trail."""
    from platform.features.billing.commerce.invoice.models import Invoice
    from platform.features.billing.commerce.payments.models import Charge

    if Charge.objects.filter(
        company=company,
        status__in=_SETTLED_CHARGE_STATUSES,
    ).exists():
        return True
    return Invoice.objects.filter(
        company=company,
        status=Invoice.InvoiceStatus.PAID,
    ).exists()


def _clear_public_billing(company) -> None:
    """Delete public billing rows whose FKs to Company/PaymentMethod are DO_NOTHING.

    PaymentMethod and CompanySubscription CASCADE from Company. Charges must
    go first or CASCADE on payment methods hits ``billing_charges``.
    """
    from platform.features.billing.commerce.invoice.models import Invoice
    from platform.features.billing.commerce.payments.models import Charge, ChargeAttempt, WebhookInbox
    from platform.features.billing.commerce.promotion.models import (
        PromotionBenefit,
        PromotionRedemption,
        PromotionVoucher,
    )

    charge_ids = list(
        Charge.objects.filter(company=company).values_list('id', flat=True),
    )
    if charge_ids:
        ChargeAttempt.objects.filter(charge_id__in=charge_ids).delete()
        WebhookInbox.objects.filter(charge_id__in=charge_ids).update(charge_id=None)
        Charge.objects.filter(id__in=charge_ids).delete()

    Invoice.objects.filter(company=company).delete()
    PromotionBenefit.objects.filter(company=company).delete()
    PromotionRedemption.objects.filter(company=company).delete()
    PromotionVoucher.objects.filter(company=company).delete()


@dataclass(frozen=True)
class UnverifiedTenantsPurgeResult:
    """Counts of rows removed by the sweep.

    Frozen so the caller (mgmt command, Celery task, tests) cannot
    mutate the audit trail by mistake.
    """
    tenants_deleted: int
    users_deleted: int


class PurgeUnverifiedTenantsUseCase:
    """Delete Companies whose entire user population is unverified.

    Stateless and free of transport concerns (no Celery, no Django
    management plumbing), mirroring ``PurgeExpiredOnboardingsUseCase``.
    """

    def __init__(self, retention_days: int = 7):
        self.retention_days = retention_days

    @trace_layer('application')
    def execute(self, dry_run: bool = False) -> UnverifiedTenantsPurgeResult:
        # Lazy imports keep the use case decoupled at module load time —
        # the same trick ``finalize`` uses.
        from client.features.security.lifecycle.registration.models import User
        from platform.features.company.tenant.company.models import Company

        cutoff = timezone.now().date() - timedelta(days=self.retention_days)

        # A Company is "abandoned & unverified" iff:
        #   - it has at least one User (so we don't accidentally nuke the
        #     public schema row or any other zero-user system tenant), AND
        #   - none of its Users have email_verified_at set.
        candidates_qs = (
            Company.objects
            .annotate(
                total_users=Count('user'),
                verified_users=Count(
                    'user', filter=Q(user__email_verified_at__isnull=False),
                ),
            )
            .filter(
                total_users__gt=0,
                verified_users=0,
                created__lte=cutoff,
                lifecycle='ACTIVE',
            )
            # Public schema is never a real tenant Company in this codebase
            # (Company == client tenant), but defend in depth.
            .exclude(schema_name='public')
        )

        if dry_run:
            tenants = candidates_qs.count()
            users = User.objects.filter(company__in=candidates_qs).count()
            return UnverifiedTenantsPurgeResult(
                tenants_deleted=tenants, users_deleted=users,
            )

        tenants_deleted = 0
        users_deleted = 0

        # Materialise the queryset before iteration so the .delete() calls
        # below can't accidentally affect later iterations.
        for company in list(candidates_qs):
            try:
                if _has_settled_billing(company):
                    logger.warning(
                        'purge_unverified_tenants: skipped tenant with settled billing',
                        extra={
                            'company_id': str(company.id),
                            'schema_name': company.schema_name,
                        },
                    )
                    continue
                with transaction.atomic():
                    _clear_public_billing(company)
                    deleted_users, _ = User.objects.filter(company=company).delete()
                    # ``force_drop=True`` makes django-tenants run
                    # ``DROP SCHEMA <name> CASCADE`` and delete the row
                    # in a single sequence; CASCADE on Domain.tenant
                    # handles domain rows automatically.
                    company.delete(force_drop=True)
                    users_deleted += deleted_users
                    tenants_deleted += 1
                logger.info(
                    'purge_unverified_tenants: dropped tenant',
                    extra={
                        'company_id': str(company.id),
                        'schema_name': company.schema_name,
                        'users_deleted': deleted_users,
                    },
                )
            except Exception:
                # Per-tenant failures (e.g. a row got verified between
                # query and delete) should not abort the whole sweep.
                logger.exception(
                    'purge_unverified_tenants: failed to drop tenant',
                    extra={
                        'company_id': str(company.id),
                        'schema_name': company.schema_name,
                    },
                )

        return UnverifiedTenantsPurgeResult(
            tenants_deleted=tenants_deleted,
            users_deleted=users_deleted,
        )
