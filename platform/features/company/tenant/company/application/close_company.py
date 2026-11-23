from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.application.export_company import ExportClosedTenantUseCase
from platform.features.company.tenant.company.application.purge_company import PurgeClosedCompanyUseCase
from platform.features.company.tenant.company.domain.interfaces import (
    ICompanyCloseNotifier,
    ICompanyOffboardingRepository,
    ITenantExportStore,
    ITenantSessionRevoker,
)
from platform.features.company.tenant.company.application.deregistration_policy import (
    RequireDeregistrationPolicySignatureUseCase,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    IMMEDIATE_PURGE_WAIVER_REASON,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CLOSED,
    LIFECYCLE_GONE,
    LIFECYCLE_PENDING_PURGE,
    PUBLIC_SCHEMA_NAME,
    SELF_CLOSE_PENDING_REASON,
)
from platform.features.company.tenant.company.domain.schemas import (
    CloseCompanySchema,
    CompleteSelfCloseSchema,
    CompanyLifecycleRecord,
    ExportClosedTenantSchema,
    PurgeClosedCompanySchema,
    ReopenCompanySchema,
    SelfCloseCompanySchema,
)
from core.trace import trace_layer


def _parse_instant(value: str):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _names_match(expected: str, given: str) -> bool:
    def normalize(value: str) -> str:
        return ' '.join((value or '').strip().split()).casefold()

    left = normalize(expected)
    return bool(left) and left == normalize(given)


def _purge_immediately(
    companies: ICompanyOffboardingRepository,
    store: ITenantExportStore,
    closed: CompanyLifecycleRecord,
    *,
    actor_admin_id,
) -> CompanyLifecycleRecord:
    try:
        ExportClosedTenantUseCase(companies, store).execute(
            ExportClosedTenantSchema(
                company_id=closed.id,
                actor_admin_id=actor_admin_id,
            ),
        )
    except Exception:
        ExportClosedTenantUseCase(companies, store).execute(
            ExportClosedTenantSchema(
                company_id=closed.id,
                waived=True,
                reason=IMMEDIATE_PURGE_WAIVER_REASON,
                actor_admin_id=actor_admin_id,
            ),
        )
    return PurgeClosedCompanyUseCase(companies, store).execute(
        PurgeClosedCompanySchema(
            company_id=closed.id,
            force=True,
            reason=IMMEDIATE_PURGE_WAIVER_REASON,
            actor_admin_id=actor_admin_id,
        ),
    )


class CloseCompanyUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        sessions: ITenantSessionRevoker,
        notifier: ICompanyCloseNotifier,
        store: ITenantExportStore | None = None,
    ):
        self.companies = companies
        self.sessions = sessions
        self.notifier = notifier
        self.store = store

    @trace_layer('application')
    def execute(self, data: CloseCompanySchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.schema_name == PUBLIC_SCHEMA_NAME:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)
        if record.lifecycle != LIFECYCLE_ACTIVE:
            raise ConflictException(AppErrorCode.COMPANY_ALREADY_CLOSED)
        if data.grace_days < 0:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_NOT_ALLOWED)

        now = timezone.now()
        purge_after = now if data.grace_days == 0 else now + timedelta(days=data.grace_days)
        closed = self.companies.apply_close(
            data.company_id,
            reason=data.reason,
            actor_admin_id=data.actor_admin_id,
            closed_at=now,
            purge_after=purge_after,
            spare_user_id=data.spare_user_id,
        )
        revoke_ids = [
            user_id for user_id in closed.user_ids
            if data.spare_user_id is None or user_id != data.spare_user_id
        ]
        try:
            self.sessions.revoke_all(revoke_ids)
        except Exception:
            pass
        try:
            self.notifier.notify_closed(closed)
        except Exception:
            pass
        if data.grace_days == 0 and data.spare_user_id is None and self.store is not None:
            return _purge_immediately(
                self.companies, self.store, closed, actor_admin_id=data.actor_admin_id,
            )
        return closed


class SelfCloseCompanyUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        sessions: ITenantSessionRevoker,
        notifier: ICompanyCloseNotifier,
        store: ITenantExportStore | None = None,
        *,
        policy_gate: RequireDeregistrationPolicySignatureUseCase,
    ):
        self.companies = companies
        self.closer = CloseCompanyUseCase(companies, sessions, notifier, store)
        self.policy_gate = policy_gate

    @trace_layer('application')
    def execute(self, data: SelfCloseCompanySchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if not _names_match(record.name, data.confirmation):
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        if not data.accepted:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED)
        self.policy_gate.execute(
            actor_user_id=data.actor_user_id,
            company_id=data.company_id,
            country=data.country,
        )
        # Zero grace: do not spare the actor. CloseCompanyUseCase then
        # deactivates every member, revokes JWTs and purges immediately.
        spare = None if data.grace_days == 0 else data.actor_user_id
        return self.closer.execute(CloseCompanySchema(
            company_id=data.company_id,
            reason=SELF_CLOSE_PENDING_REASON,
            actor_admin_id=data.actor_user_id,
            grace_days=data.grace_days,
            spare_user_id=spare,
        ))


class CompleteSelfCloseUseCase:
    def __init__(
        self,
        companies: ICompanyOffboardingRepository,
        sessions: ITenantSessionRevoker,
        store: ITenantExportStore | None = None,
    ):
        self.companies = companies
        self.sessions = sessions
        self.store = store

    @trace_layer('application')
    def execute(self, data: CompleteSelfCloseSchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.lifecycle == LIFECYCLE_GONE:
            return record
        if record.lifecycle not in (LIFECYCLE_CLOSED, LIFECYCLE_PENDING_PURGE):
            raise ConflictException(AppErrorCode.COMPANY_CANNOT_REOPEN)
        reason = (data.reason or '').strip()
        if reason:
            record = self.companies.apply_close_reason(data.company_id, reason=reason)
        self.companies.deactivate_member(data.company_id, data.actor_user_id)
        try:
            self.sessions.revoke_all([data.actor_user_id])
        except Exception:
            pass
        due = bool(record.purge_after) and timezone.now() >= _parse_instant(record.purge_after)
        if due and self.store is not None:
            return _purge_immediately(
                self.companies, self.store, record, actor_admin_id=data.actor_user_id,
            )
        return record


class ReopenCompanyUseCase:
    def __init__(self, companies: ICompanyOffboardingRepository):
        self.companies = companies

    @trace_layer('application')
    def execute(self, data: ReopenCompanySchema) -> CompanyLifecycleRecord:
        record = self.companies.get_lifecycle(data.company_id)
        if record is None:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        if record.lifecycle != LIFECYCLE_CLOSED:
            raise ConflictException(AppErrorCode.COMPANY_CANNOT_REOPEN)
        if record.legal_hold:
            raise ConflictException(AppErrorCode.COMPANY_LEGAL_HOLD)
        if not record.purge_after:
            raise ConflictException(AppErrorCode.COMPANY_GRACE_EXPIRED)
        if timezone.now() >= _parse_instant(record.purge_after):
            raise ConflictException(AppErrorCode.COMPANY_GRACE_EXPIRED)
        return self.companies.apply_reopen(data.company_id)
