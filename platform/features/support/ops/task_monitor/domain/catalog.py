"""In-code catalog of monitored automated tasks and their steps.

Schedules and step definitions change via PR — not via admin seed data.
Keys must match Celery ``@shared_task(name=...)`` and ``core.tasks.schedules``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TaskStepDef:
    key: str
    label: str
    icon: str
    order: int


@dataclass(frozen=True)
class TaskDef:
    key: str
    title: str
    description: str
    icon: str
    schedule_label: str
    group: str
    steps: tuple[TaskStepDef, ...]

    def step(self, key: str) -> Optional[TaskStepDef]:
        for s in self.steps:
            if s.key == key:
                return s
        return None


TASK_CATALOG: dict[str, TaskDef] = {
    'onboarding.purge_expired': TaskDef(
        key='onboarding.purge_expired',
        title='Purge expired onboardings',
        description=(
            'Expires abandoned registrations, deletes old failed provisioning '
            'rows, and purges stale email-confirmation tokens.'
        ),
        icon='bx-user-x',
        schedule_label='Daily 03:00 UTC',
        group='onboarding',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('expire_registrations', 'Expire registrations', 'bx-time-five', 2),
            TaskStepDef('delete_failed', 'Delete failed rows', 'bx-trash', 3),
            TaskStepDef('purge_tokens', 'Purge tokens', 'bx-key', 4),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 5),
        ),
    ),
    'onboarding.purge_unverified_tenants': TaskDef(
        key='onboarding.purge_unverified_tenants',
        title='Purge unverified tenants',
        description=(
            'Drops companies whose admin never confirmed email and were '
            'created more than the retention window ago.'
        ),
        icon='bx-building-house',
        schedule_label='Daily 03:30 UTC',
        group='onboarding',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('purge_tenants', 'Purge tenants', 'bx-trash', 2),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 3),
        ),
    ),
    'company.purge_closed_tenants': TaskDef(
        key='company.purge_closed_tenants',
        title='Purge closed tenants',
        description=(
            'Purges CLOSED companies past the grace window when export is '
            'attested and no legal hold is set.'
        ),
        icon='bx-building',
        schedule_label='Daily 03:45 UTC',
        group='company',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('purge_tenants', 'Purge tenants', 'bx-trash', 2),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 3),
        ),
    ),
    'subscription.apply_pending_downgrades': TaskDef(
        key='subscription.apply_pending_downgrades',
        title='Apply pending downgrades',
        description=(
            'Materialises scheduled subscription downgrades for acquisitions '
            'past vigencia with a pending lower plan.'
        ),
        icon='bx-downvote',
        schedule_label='Daily 04:00 UTC',
        group='billing',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('load_due', 'Load due companies', 'bx-list-ul', 2),
            TaskStepDef('apply_downgrades', 'Apply downgrades', 'bx-transfer', 3),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 4),
        ),
    ),
    'subscription.renew_due_subscriptions': TaskDef(
        key='subscription.renew_due_subscriptions',
        title='Renew due subscriptions',
        description=(
            'Renews active acquisitions past vigencia with auto_renew enabled '
            'and no pending plan change.'
        ),
        icon='bx-refresh',
        schedule_label='Daily 04:15 UTC',
        group='billing',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('load_due', 'Load due companies', 'bx-list-ul', 2),
            TaskStepDef('renew_companies', 'Renew companies', 'bx-credit-card', 3),
            TaskStepDef('expire_stale', 'Expire stale periods', 'bx-time-five', 4),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 5),
        ),
    ),
    'promotion.expire_vouchers': TaskDef(
        key='promotion.expire_vouchers',
        title='Expire promotion vouchers',
        description=(
            'Marks ACTIVE vouchers past redeem_valid_until as EXPIRED.'
        ),
        icon='bx-purchase-tag-alt',
        schedule_label='Daily 04:30 UTC',
        group='billing',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('expire_vouchers', 'Expire vouchers', 'bx-time-five', 2),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 3),
        ),
    ),
    'promotion.revert_gift_benefits': TaskDef(
        key='promotion.revert_gift_benefits',
        title='Revert expired gift benefits',
        description=(
            'Reverts gift benefits whose benefit_end has passed '
            '(restores previous plan when recorded).'
        ),
        icon='bx-gift',
        schedule_label='Daily 04:45 UTC',
        group='billing',
        steps=(
            TaskStepDef('acquire_lock', 'Acquire lock', 'bx-lock-alt', 1),
            TaskStepDef('revert_benefits', 'Revert benefits', 'bx-undo', 2),
            TaskStepDef('release', 'Release lock', 'bx-lock-open-alt', 3),
        ),
    ),
    'invoice.reconcile_fiscal_pending': TaskDef(
        key='invoice.reconcile_fiscal_pending',
        title='Reconcile pending fiscal invoices',
        description=(
            'Pulls Neurana status for base invoices stuck in fiscal_status=pending '
            'or voiding (Phase 4). No-op when INVOICING_PROVIDER=local.'
        ),
        icon='bx-receipt',
        schedule_label='Daily 05:00 UTC',
        group='billing',
        steps=(
            TaskStepDef('scan_pending', 'Scan pending', 'bx-list-ul', 1),
            TaskStepDef('pull_neurana', 'Pull Neurana', 'bx-cloud-download', 2),
            TaskStepDef('update_rows', 'Update rows', 'bx-edit', 3),
        ),
    ),
}


def get_task_def(task_key: str) -> Optional[TaskDef]:
    return TASK_CATALOG.get(task_key)


def list_task_defs() -> list[TaskDef]:
    return list(TASK_CATALOG.values())
