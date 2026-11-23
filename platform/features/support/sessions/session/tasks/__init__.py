"""Support-session Celery tasks.

Exposed task names (referenced by Beat):

  * ``support.expire_stale_sessions``

Celery's :func:`autodiscover_tasks` imports ``<app>.tasks`` once; it does
**not** recurse into submodules. Re-export here so decorators register.
"""

from .expire_stale import expire_stale_support_sessions  # noqa: F401

__all__ = [
    'expire_stale_support_sessions',
]
