"""Promotion-feature Celery tasks.

Exposed task names (referenced by Beat):

  * ``promotion.expire_vouchers``
  * ``promotion.revert_gift_benefits``

Celery's :func:`autodiscover_tasks` imports ``<app>.tasks`` once; it does
**not** recurse into submodules. Re-export here so decorators register.
"""

from .expiry import (  # noqa: F401
    expire_promotion_vouchers_task,
    revert_expired_gift_benefits_task,
)

__all__ = [
    'expire_promotion_vouchers_task',
    'revert_expired_gift_benefits_task',
]
