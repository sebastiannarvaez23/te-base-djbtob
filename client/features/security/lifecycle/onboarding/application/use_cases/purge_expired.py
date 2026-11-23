"""Garbage-collect onboarding records and email-confirmation tokens.

Three independent sweeps:

  1. ``IN_PROGRESS`` registrations past ``expires_at``:
        status → ``EXPIRED`` and PII JSON fields cleared. The row is
        kept for downstream metrics; only the personal data is wiped.

  2. ``FAILED_PROVISIONING`` registrations older than
     ``failed_retention_days``:
        hard-deleted. They cannot be resumed and would otherwise retain
        PII indefinitely.

  3. Email-confirmation tokens that are consumed (``used_at IS NOT NULL``)
     or expired (``expires_at <= now``) and older than
     ``token_retention_days``:
        hard-deleted.

The use case is **idempotent**: running it twice in a row produces
``(N, 0, 0)`` then ``(0, 0, 0)``. This matters because both the
management command and the Celery Beat task call into it; concurrent
or duplicate executions must be safe.

Each sweep is a single ``UPDATE``/``DELETE`` filtered on indexed
columns (status + timestamp), so the job stays fast even with large
tables and never holds long row locks. Safe to run alongside the live
API.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from core.trace import trace_layer


_PII_FIELDS = ('company_data', 'admin_user_data', 'subscription_data', 'payment_data')


@dataclass(frozen=True)
class PurgeResult:
    """Counts of rows touched by each sweep.

    Returned to whoever invoked the use case (management command or
    Celery task) so they can log/audit the operation. Frozen so callers
    cannot mutate the audit trail by accident.
    """
    expired: int
    failed_deleted: int
    tokens_deleted: int


class PurgeExpiredOnboardingsUseCase:
    """Application use case for the onboarding GC sweep.

    Stateless and free of any transport concerns (no Celery, no Django
    management plumbing). Both ``purge_expired_onboardings`` (mgmt
    command) and the Celery task call ``execute()`` and forward the
    result to their respective logging destinations.
    """

    def __init__(
        self,
        failed_retention_days: int = 30,
        token_retention_days: int = 7,
    ):
        self.failed_retention_days = failed_retention_days
        self.token_retention_days = token_retention_days

    @trace_layer('application')
    def execute(self, dry_run: bool = False) -> PurgeResult:
        now = timezone.now()
        failed_cutoff = now - timedelta(days=self.failed_retention_days)
        token_cutoff = now - timedelta(days=self.token_retention_days)

        return PurgeResult(
            expired=self.expire_in_progress(now, dry_run),
            failed_deleted=self.delete_old_failed(failed_cutoff, dry_run),
            tokens_deleted=self.delete_old_tokens(token_cutoff, dry_run),
        )

    # ── sweeps ──────────────────────────────────────────────────────────

    @trace_layer('application')
    def expire_in_progress(self, now, dry_run: bool) -> int:
        from client.features.security.lifecycle.onboarding.models import CompanyRegistration

        qs = CompanyRegistration.objects.filter(
            status=CompanyRegistration.Status.IN_PROGRESS,
            expires_at__lte=now,
        )
        if dry_run:
            return qs.count()

        with transaction.atomic():
            pii_clear = {f: {} for f in _PII_FIELDS}
            return qs.update(
                status=CompanyRegistration.Status.EXPIRED,
                **pii_clear,
            )

    @trace_layer('application')
    def delete_old_failed(self, cutoff, dry_run: bool) -> int:
        from client.features.security.lifecycle.onboarding.models import CompanyRegistration

        qs = CompanyRegistration.objects.filter(
            status=CompanyRegistration.Status.FAILED_PROVISIONING,
            updated_at__lte=cutoff,
        )
        if dry_run:
            return qs.count()

        count, _ = qs.delete()
        return count

    @trace_layer('application')
    def delete_old_tokens(self, cutoff, dry_run: bool) -> int:
        from client.features.security.lifecycle.auth.models import EmailConfirmationToken

        qs = EmailConfirmationToken.objects.filter(
            Q(used_at__lte=cutoff) | Q(used_at__isnull=True, expires_at__lte=cutoff),
        )
        if dry_run:
            return qs.count()

        count, _ = qs.delete()
        return count
