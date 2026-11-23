"""Onboarding-feature Celery tasks.

Exposed task names (referenced by Beat / .delay() callers):

  * ``onboarding.purge_expired`` — daily GC sweep for expired/failed
    onboarding rows and stale email-confirmation tokens. Scheduled
    in :mod:`core.tasks.schedules`.
  * ``onboarding.purge_unverified_tenants`` — daily GC sweep for
    finalised tenants whose admin user never confirmed their email.
    Scheduled in :mod:`core.tasks.schedules`.

Task modules import use cases from ``..application.use_cases`` and stay
free of business logic. Adding a task here ≈ adding an APIView: pick
the use case, wire its arguments, log the outcome.

Celery's :func:`autodiscover_tasks` imports ``<app>.tasks`` once; it
does **not** recurse into submodules of a ``tasks/`` package. Each new
task module therefore has to be re-exported from this ``__init__`` so
the ``@shared_task`` decorators run and the task names get registered.
"""

from .purge import purge_expired_onboardings  # noqa: F401  — registers task
from .purge_unverified_tenants import purge_unverified_tenants  # noqa: F401

__all__ = ['purge_expired_onboardings', 'purge_unverified_tenants']
