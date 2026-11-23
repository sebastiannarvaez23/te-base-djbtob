"""Static Celery Beat schedule for system-maintenance tasks.

Hard-coded in version control on purpose: these are deployment-level
jobs (purges, sweeps) that should change via PR, not via admin. If the
project later needs operator-editable schedules (per-tenant cadences),
``redbeat`` already supports both modes simultaneously — additional
entries can come from Redis without touching this file.

Conventions for new entries:

  * Pick task names of the form ``<feature>.<verb>``. Beat references
    them by string, so they must match the ``name=`` of the
    ``@shared_task`` declaration.
  * Always set ``options['expires']``. Without it, a Beat outage
    followed by a recovery floods the worker with backlogged
    occurrences. The expiry should be a small multiple of the cadence
    (1.5–6× usually).
  * UTC-anchored (the Celery process honours ``CELERY_TIMEZONE``).
    Don't rely on local time — multi-region deployments break.
"""

from celery.schedules import crontab

_DEFAULT_FISCAL_RELAY_INTERVAL = 30.0


def build_beat_schedule(*, fiscal_relay_interval: float = _DEFAULT_FISCAL_RELAY_INTERVAL) -> dict:
    """Build the Beat map of system-maintenance jobs.

    ``fiscal_relay_interval`` is passed in from settings so this module
    never reads ``django.conf.settings`` while ``base.py`` is still
    importing (that nested setup was emitting Django's USE_TZ warning).
    """
    return {
        # Daily 03:00 UTC — sweeps abandoned IN_PROGRESS registrations,
        # hard-deletes old FAILED_PROVISIONING rows, and purges consumed
        # email-confirmation tokens. Each sweep is a single
        # ``UPDATE``/``DELETE`` indexed on status + timestamp, so the job
        # is fast even with millions of rows. The 6h ``expires`` means a
        # half-day Beat outage still produces at most one make-up run.
        'onboarding-purge-expired-daily': {
            'task':     'onboarding.purge_expired',
            'schedule': crontab(hour=3, minute=0),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 03:30 UTC — drops Companies whose admin user never
        # confirmed their email and were created more than 7 days ago.
        # Scheduled 30 min after ``purge_expired`` on purpose: the two
        # sweeps touch different tables but contend for the same audit-log
        # write throughput; serialising them keeps log noise low and avoids
        # any per-row lock interaction in edge cases. Same 6h expiry: a
        # half-day Beat outage still produces at most one make-up run.
        'onboarding-purge-unverified-tenants-daily': {
            'task':     'onboarding.purge_unverified_tenants',
            'schedule': crontab(hour=3, minute=30),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 03:45 UTC — purges CLOSED tenants past grace with export
        # attested and no legal hold. Runs after unverified GC so the jobs
        # never compete for the same company row. Same 6h expiry.
        'company-purge-closed-tenants-daily': {
            'task':     'company.purge_closed_tenants',
            'schedule': crontab(hour=3, minute=45),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 04:00 UTC — materialises scheduled subscription downgrades: for
        # acquisitions whose vigencia has passed with a pending (lower) plan, it
        # charges that plan and starts a new acquisition (+30 days). Same 6h
        # expiry so a half-day Beat outage still yields at most one make-up run.
        'subscription-apply-pending-downgrades-daily': {
            'task':     'subscription.apply_pending_downgrades',
            'schedule': crontab(hour=4, minute=0),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 04:15 UTC — recurring renewals: for active acquisitions past their
        # vigencia with no pending change and auto_renew on, charges the same plan
        # and extends (+30). Runs 15 min after the downgrade sweep so the two
        # disjoint sets never contend. Same 6h expiry.
        'subscription-renew-due-daily': {
            'task':     'subscription.renew_due_subscriptions',
            'schedule': crontab(hour=4, minute=15),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 04:30 UTC — mark ACTIVE vouchers past redeem_valid_until as EXPIRED.
        'promotion-expire-vouchers-daily': {
            'task':     'promotion.expire_vouchers',
            'schedule': crontab(hour=4, minute=30),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Daily 04:45 UTC — revert gift benefits whose benefit_end has passed
        # (restore previous plan when recorded). Runs after expire so status
        # transitions stay ordered.
        'promotion-revert-gift-benefits-daily': {
            'task':     'promotion.revert_gift_benefits',
            'schedule': crontab(hour=4, minute=45),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },

        # Every minute — cancel QUEUED support sessions past queue_wait_timeout
        # and close AWAITING_RATING past the rating TTL. Cheap indexed scans;
        # 90s expires so a short Beat outage yields at most one make-up run.
        'support-expire-stale-sessions': {
            'task':     'support.expire_stale_sessions',
            'schedule': 60.0,
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 90},
        },

        # Fiscal outbox → Neurana. Rows are leased (skip locked), so an
        # overlapping run never double-sends; backoff lives in the use case.
        'billing-fiscal-outbox-relay': {
            'task':     'billing.fiscal_outbox.relay',
            'schedule': float(fiscal_relay_interval),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60},
        },

        # Every 5 min — bell alerts for a stale fiscal backlog / dead letters.
        'billing-fiscal-outbox-check-health': {
            'task':     'billing.fiscal_outbox.check_health',
            'schedule': 300.0,
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 600},
        },

        # Daily 05:00 UTC — safety net: poll Neurana for pending documents and
        # re-enqueue commands the outbox never received. No-op when local.
        'invoice-reconcile-fiscal-pending-daily': {
            'task':     'invoice.reconcile_fiscal_pending',
            'schedule': crontab(hour=5, minute=0),
            'args':     (),
            'kwargs':   {},
            'options':  {'expires': 60 * 60 * 6},
        },
    }


# Lazily populated alias for docs/imports; prefer ``build_beat_schedule()``.
def __getattr__(name: str):
    if name == 'BEAT_SCHEDULE':
        return build_beat_schedule()
    raise AttributeError(name)
