"""Cross-cutting Celery infrastructure.

This package owns the Celery application, the base task classes, and the
distributed-lock helpers that feature-level tasks build on. It is the
*infrastructure* of the task transport — feature ``tasks/`` packages
import from here, never the other way around.

Public surface:

  * :func:`core.tasks.app.app` — the configured Celery application.
  * :class:`core.tasks.base.BaseTask` — retry policy + structured logging.
  * :class:`core.tasks.base.RetryableTaskError` — opt-in domain autoretry.
  * :class:`core.tasks.base.TenantTask` — adds ``schema_name`` kwarg
    handling for django-tenants.
  * :func:`core.tasks.base.redis_lock` — context manager for SETNX-style
    locks that prevent concurrent execution of the same job.
  * :func:`core.tasks.run_context.track_task_run` — monitored run/steps
    + LIFO compensations (generic rollback) on failure.
  * :func:`core.tasks.schedules.build_beat_schedule` — wired into
    ``CELERY_BEAT_SCHEDULE`` in settings.
"""

from .app import app as celery_app

__all__ = ['celery_app']
