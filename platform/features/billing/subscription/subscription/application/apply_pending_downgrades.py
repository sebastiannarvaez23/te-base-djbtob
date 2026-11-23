"""
ApplyPendingDowngradesUseCase — materialises scheduled downgrades.

When a company's acquisition reaches its end_date with a pending (lower) plan
recorded, this charges that plan and activates it (new vigencia matching the
pending billing interval: 30 days monthly / 365 yearly). The charge drives
the usual invoice + email (SUB_INVOICING).

Two callers, same per-company unit of work (so they share the per-company lock
held by the task layer and never double-charge):
  * daily sweep ``subscription.apply_pending_downgrades`` — for inactive accounts.
  * lazy ``subscription.apply_pending_downgrade_for_company`` — enqueued by the
    access middleware on the first request after vigencia, for active users.
"""
import logging
from typing import List
from core.trace import trace_layer

logger = logging.getLogger('app.tasks')


class ApplyPendingDowngradesUseCase:

    def __init__(self, repo, change_use_case, directory=None):
        self._repo = repo
        self._change = change_use_case
        if directory is None:
            from platform.features.billing.common.directory import DjangoBillingDirectory
            directory = DjangoBillingDirectory()
        self._directory = directory

    @trace_layer('application')
    def due_company_ids(self) -> List:
        """Companies whose vigencia passed with a pending downgrade."""
        return [r.company_id for r in self._repo.list_pending_downgrades_due()]

    @trace_layer('application')
    def apply_for_company(self, company_id) -> bool:
        """Charge + activate the pending downgrade for ONE company. Idempotent:
        re-reads the due pending plan, so once the switch happened (old
        closed, new active without pending) a second call is a no-op.

        Returns True if a change was applied, False otherwise (nothing due or
        no payment method). Raises on a gateway/charge error — the task layer
        logs it and moves on.
        """
        pending_id = self._repo.get_due_pending_downgrade(company_id)
        if pending_id is None:
            return False
        card = self._directory.active_card(company_id)
        if card is None:
            logger.warning(
                'pending downgrade skipped for company %s: no payment method on file',
                company_id,
            )
            return False
        self._change.apply_scheduled_change(
            company_id, pending_id, card.id,
            billing_interval=self._repo.pending_billing_interval(company_id),
        )
        return True
