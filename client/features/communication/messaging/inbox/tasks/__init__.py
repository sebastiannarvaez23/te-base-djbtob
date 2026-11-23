"""Inbox Celery tasks.

Exposed task names:

  * ``inbox.process_outbox_fanout`` — materializa un
    ``AdminNotificationOutbox`` en los schemas de tenant (campanita).

Celery's :func:`autodiscover_tasks` imports ``<app>.tasks`` once; it
does **not** recurse into submodules of a ``tasks/`` package. Each task
module must be re-exported from this ``__init__`` so the
``@shared_task`` decorators run and the names get registered.
"""

from .fanout import process_outbox_fanout  # noqa: F401 — registers task

__all__ = ['process_outbox_fanout']
