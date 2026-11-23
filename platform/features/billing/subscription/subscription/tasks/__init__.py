"""Subscription-feature Celery tasks.

Exposed task names (referenced by Beat / .delay() callers):

  * ``subscription.apply_pending_downgrades`` — daily sweep that charges +
    activates pending downgrades whose vigencia has passed. Scheduled in
    :mod:`core.tasks.schedules`.

Celery's :func:`autodiscover_tasks` imports ``<app>.tasks`` once; it does
**not** recurse into submodules. Each task module must be re-exported here so
the ``@shared_task`` decorators run and the task names get registered.
"""

from .downgrades import (  # noqa: F401  — registers tasks
    apply_pending_downgrades,
    apply_pending_downgrade_for_company,
)
from .expire import (  # noqa: F401  — registers tasks
    expire_subscription_for_company,
)
from .renewals import (  # noqa: F401  — registers tasks
    renew_due_subscriptions,
    renew_subscription_for_company,
)

__all__ = [
    'apply_pending_downgrades',
    'apply_pending_downgrade_for_company',
    'expire_subscription_for_company',
    'renew_due_subscriptions',
    'renew_subscription_for_company',
]
