from __future__ import annotations

import logging
from uuid import UUID

from core.errors import AppErrorCode, ConflictException, NotFoundException
from django.contrib.auth import get_user_model
from django.db import transaction
from django_tenants.utils import schema_exists

from core.auth.refresh_service import revoke_all_for_users
from platform.features.billing.subscription.subscription.infrastructure.repositories import (
    _invalidate_access_cache,
)
from platform.features.billing.subscription.subscription.models import CompanySubscription
from platform.features.communication.notification.dispatchers import (
    dispatch_company_deregistration,
)
from platform.features.company.tenant.company.domain.interfaces import (
    ICompanyCloseNotifier,
    ICompanyOffboardingRepository,
    ITenantSessionRevoker,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CLOSED,
    LIFECYCLE_GONE,
    LIFECYCLE_PENDING_PURGE,
    PUBLIC_SCHEMA_NAME,
    TOMBSTONE_EMAIL_DOMAIN,
)
from platform.features.company.tenant.company.domain.schemas import CompanyLifecycleRecord
from platform.features.company.tenant.company.models import ClosedTenantRecord, Company

logger = logging.getLogger('app.company')


def _user_ids(company_id: UUID) -> list[UUID]:
    User = get_user_model()
    return list(User.objects.filter(company_id=company_id).values_list('id', flat=True))


def _lock_company(company_id: UUID) -> Company:
    try:
        return Company.objects.select_for_update().get(id=company_id)
    except Company.DoesNotExist as exc:
        raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND) from exc


def _cancel_current_subscription(company_id: UUID) -> None:
    acquisition = (
        CompanySubscription.objects
        .filter(
            company_id=company_id,
            status__in=[
                CompanySubscription.Status.ACTIVE,
                CompanySubscription.Status.SUSPENDED,
            ],
        )
        .order_by('-start_date')
        .first()
    )
    if acquisition is None:
        return
    acquisition.status = CompanySubscription.Status.CANCELLED
    acquisition.save(update_fields=['status'])


def _restore_cancelled_subscription(company_id: UUID) -> None:
    acquisition = (
        CompanySubscription.objects
        .filter(company_id=company_id, status=CompanySubscription.Status.CANCELLED)
        .order_by('-start_date')
        .first()
    )
    if acquisition is None:
        return
    acquisition.status = CompanySubscription.Status.ACTIVE
    acquisition.save(update_fields=['status'])


def _to_record(company: Company, user_ids: list[UUID] | None = None) -> CompanyLifecycleRecord:
    return CompanyLifecycleRecord(
        id=company.id,
        schema_name=company.schema_name,
        nit=company.nit or '',
        name=company.name,
        lifecycle=company.lifecycle,
        closed_at=company.closed_at.isoformat() if company.closed_at else None,
        purge_after=company.purge_after.isoformat() if company.purge_after else None,
        closed_reason=company.closed_reason or '',
        legal_hold=bool(company.legal_hold),
        legal_hold_reason=company.legal_hold_reason or '',
        export_attested_at=(
            company.export_attested_at.isoformat() if company.export_attested_at else None
        ),
        export_object_key=company.export_object_key or '',
        export_attested_by=company.export_attested_by,
        user_ids=user_ids if user_ids is not None else _user_ids(company.id),
        users_tombstoned=company.users_tombstoned,
    )


class DjangoCompanyOffboardingRepository(ICompanyOffboardingRepository):
    def get_lifecycle(self, company_id: UUID) -> CompanyLifecycleRecord | None:
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return None
        return _to_record(company)

    def apply_close(
        self,
        company_id: UUID,
        *,
        reason: str,
        actor_admin_id: UUID | None,
        closed_at,
        purge_after,
        spare_user_id: UUID | None = None,
    ) -> CompanyLifecycleRecord:
        User = get_user_model()
        with transaction.atomic():
            company = _lock_company(company_id)
            if company.lifecycle != LIFECYCLE_ACTIVE:
                raise ConflictException(AppErrorCode.COMPANY_ALREADY_CLOSED)
            company.lifecycle = LIFECYCLE_CLOSED
            company.closed_at = closed_at
            company.purge_after = purge_after
            company.closed_reason = reason
            company.closed_by_admin_id = actor_admin_id
            company.save(update_fields=[
                'lifecycle',
                'closed_at',
                'purge_after',
                'closed_reason',
                'closed_by_admin_id',
            ])
            members = User.objects.filter(company_id=company_id, is_active=True)
            if spare_user_id is not None:
                members = members.exclude(pk=spare_user_id)
            members.update(
                is_active=False,
                deactivated_by_company_close=True,
            )
            _cancel_current_subscription(company_id)
            _invalidate_access_cache(company_id)
            ids = _user_ids(company_id)
        return _to_record(company, ids)

    def apply_close_reason(self, company_id: UUID, *, reason: str) -> CompanyLifecycleRecord:
        with transaction.atomic():
            company = _lock_company(company_id)
            company.closed_reason = reason
            company.save(update_fields=['closed_reason'])
        return _to_record(company)

    def deactivate_member(self, company_id: UUID, user_id: UUID) -> None:
        User = get_user_model()
        User.objects.filter(id=user_id, company_id=company_id).update(
            is_active=False,
            deactivated_by_company_close=True,
        )

    def apply_reopen(self, company_id: UUID) -> CompanyLifecycleRecord:
        User = get_user_model()
        with transaction.atomic():
            company = _lock_company(company_id)
            if company.lifecycle != LIFECYCLE_CLOSED:
                raise ConflictException(AppErrorCode.COMPANY_CANNOT_REOPEN)
            company.lifecycle = LIFECYCLE_ACTIVE
            company.closed_at = None
            company.purge_after = None
            company.closed_reason = ''
            company.closed_by_admin_id = None
            company.save(update_fields=[
                'lifecycle',
                'closed_at',
                'purge_after',
                'closed_reason',
                'closed_by_admin_id',
            ])
            User.objects.filter(
                company_id=company_id,
                deactivated_by_company_close=True,
            ).update(
                is_active=True,
                deactivated_by_company_close=False,
            )
            _restore_cancelled_subscription(company_id)
            _invalidate_access_cache(company_id)
            ids = _user_ids(company_id)
        return _to_record(company, ids)

    def apply_legal_hold(
        self,
        company_id: UUID,
        *,
        enabled: bool,
        reason: str,
    ) -> CompanyLifecycleRecord:
        with transaction.atomic():
            company = _lock_company(company_id)
            company.legal_hold = bool(enabled)
            company.legal_hold_reason = reason if enabled else ''
            company.save(update_fields=['legal_hold', 'legal_hold_reason'])
        return _to_record(company)

    def apply_export_attestation(
        self,
        company_id: UUID,
        *,
        actor_admin_id: UUID | None,
        attested_at,
        object_key: str,
    ) -> CompanyLifecycleRecord:
        with transaction.atomic():
            company = _lock_company(company_id)
            company.export_attested_at = attested_at
            company.export_attested_by = actor_admin_id
            company.export_object_key = object_key or ''
            company.save(update_fields=[
                'export_attested_at',
                'export_attested_by',
                'export_object_key',
            ])
        return _to_record(company)

    def list_export_users(self, company_id: UUID) -> list[dict]:
        User = get_user_model()
        rows = (
            User.objects
            .filter(company_id=company_id)
            .select_related('rol')
            .order_by('email')
            .values('id', 'email', 'username', 'first_name', 'last_name', 'is_active', 'rol__name')
        )
        return [
            {
                'id': str(row['id']),
                'email': row['email'],
                'username': row['username'],
                'first_name': row['first_name'] or '',
                'last_name': row['last_name'] or '',
                'role': row['rol__name'] or '',
                'is_active': row['is_active'],
            }
            for row in rows
        ]

    def list_purge_candidates(self, *, now) -> list[CompanyLifecycleRecord]:
        qs = (
            Company.objects
            .filter(
                lifecycle__in=[LIFECYCLE_CLOSED, LIFECYCLE_PENDING_PURGE],
                legal_hold=False,
                export_attested_at__isnull=False,
                purge_after__lte=now,
            )
            .exclude(schema_name=PUBLIC_SCHEMA_NAME)
            .order_by('purge_after')
        )
        return [_to_record(company, user_ids=[]) for company in qs]

    def mark_pending_purge(self, company_id: UUID) -> CompanyLifecycleRecord:
        with transaction.atomic():
            company = _lock_company(company_id)
            if company.lifecycle == LIFECYCLE_GONE:
                return _to_record(company)
            company.lifecycle = LIFECYCLE_PENDING_PURGE
            company.save(update_fields=['lifecycle'])
        return _to_record(company)

    def apply_purge(
        self,
        company_id: UUID,
        *,
        now,
        dry_run: bool,
    ) -> CompanyLifecycleRecord:
        with transaction.atomic():
            company = _lock_company(company_id)
            if company.lifecycle == LIFECYCLE_GONE:
                return _to_record(company)
            if dry_run:
                return _to_record(company)
            tombstoned = _tombstone_users(company_id)
            _detach_fiscal_rows(company)
            _ensure_closed_record(company, now=now, tombstoned=tombstoned)
            fiscal_nit = company.nit or ''
        dropped = _drop_tenant_schema(company)
        with transaction.atomic():
            company = _lock_company(company_id)
            company.lifecycle = LIFECYCLE_GONE
            company.nit = ''
            company.users_tombstoned = tombstoned
            company.save(update_fields=['lifecycle', 'nit', 'users_tombstoned'])
            ClosedTenantRecord.objects.filter(company_id=company_id).update(
                purged_at=now,
                users_tombstoned=tombstoned,
                schema_dropped=dropped,
                nit=fiscal_nit,
            )
        _clear_auth_satellites(company_id)
        _invalidate_access_cache(company_id)
        return _to_record(company)


class RedisTenantSessionRevoker(ITenantSessionRevoker):
    def revoke_all(self, user_ids: list[UUID]) -> int:
        return revoke_all_for_users(user_ids, 'client')


class EmailCompanyCloseNotifier(ICompanyCloseNotifier):
    """Best-effort COMPANY_DEREGISTRATION to each company administrator."""

    def notify_closed(self, record: CompanyLifecycleRecord) -> None:
        User = get_user_model()
        admins = list(
            User.objects
            .filter(company_id=record.id, rol__name='Administrator')
            .exclude(email='')
            .order_by('email')
        )
        if not admins:
            logger.warning(
                'Company close has no administrator email company_id=%s',
                record.id,
            )
            return
        for admin in admins:
            dispatch_company_deregistration(
                user=admin,
                company_name=record.name,
                company_nit=record.nit,
                closed_at=record.closed_at,
                reason=record.closed_reason,
            )


# Backwards-compatible alias used by earlier close wiring.
LoggingCompanyCloseNotifier = EmailCompanyCloseNotifier


def _tombstone_users(company_id: UUID) -> int:
    User = get_user_model()
    count = 0
    for user in User.objects.filter(company_id=company_id):
        if str(user.email).endswith(f'@{TOMBSTONE_EMAIL_DOMAIN}'):
            count += 1
            continue
        token = user.id.hex
        user.email = f'closed_{token}@{TOMBSTONE_EMAIL_DOMAIN}'
        user.username = f'closed_{token}'
        user.first_name = ''
        user.last_name = ''
        user.second_name = ''
        user.second_last_name = ''
        user.telephone = ''
        user.document_number = ''
        user.document_type = ''
        user.picture = None
        user.is_active = False
        user.deactivated_by_company_close = False
        user.set_unusable_password()
        user.save()
        count += 1
    return count


def _clear_auth_satellites(company_id: UUID) -> None:
    User = get_user_model()
    ids = list(User.objects.filter(company_id=company_id).values_list('id', flat=True))
    if not ids:
        return
    from client.features.security.lifecycle.auth.models import (
        EmailConfirmationToken,
        PasswordRecoveryToken,
        TrustedDevice,
    )
    EmailConfirmationToken.objects.filter(user_id__in=ids).delete()
    PasswordRecoveryToken.objects.filter(user_id__in=ids).delete()
    TrustedDevice.objects.filter(user_id__in=ids).delete()


def _detach_fiscal_rows(company: Company) -> None:
    from platform.features.billing.commerce.invoice.models import Invoice
    from platform.features.billing.commerce.payments.models import Charge

    Invoice.objects.filter(company=company).filter(tenant_nit='').update(tenant_nit=company.nit or '')
    Invoice.objects.filter(company=company).filter(tenant_name='').update(tenant_name=company.name)
    Invoice.objects.filter(company=company).update(company=None)
    Charge.objects.filter(company=company).filter(tenant_nit='').update(tenant_nit=company.nit or '')
    Charge.objects.filter(company=company).filter(tenant_name='').update(tenant_name=company.name)
    Charge.objects.filter(company=company).update(company=None)


def _ensure_closed_record(company: Company, *, now, tombstoned: int) -> None:
    ClosedTenantRecord.objects.update_or_create(
        company_id=company.id,
        defaults={
            'nit': company.nit or '',
            'name': company.name,
            'schema_name': company.schema_name,
            'closed_at': company.closed_at or now,
            'users_tombstoned': tombstoned,
            'schema_dropped': False,
        },
    )


def _drop_tenant_schema(company: Company) -> bool:
    schema_name = company.schema_name
    if not schema_name or schema_name == PUBLIC_SCHEMA_NAME:
        return False
    if not schema_exists(schema_name):
        return True
    from django.db import connection
    connection.set_schema_to_public()
    company._drop_schema(True)
    return not schema_exists(schema_name)
