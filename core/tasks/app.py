"""Canonical Celery application.

Workers and Beat both boot through this module:

    celery -A base worker -l info
    celery -A base beat   -l info

``base/celery.py`` re-exports this ``app`` to honour the standard Celery
discovery convention while keeping the actual configuration here in the
``core`` package — Celery is cross-cutting infrastructure, on the same
level as ``core.audit`` or ``core.errors``.

Configuration is read from ``django.conf.settings`` with the ``CELERY``
namespace, so every setting lives in ``base/settings/base.py`` next to the
rest of the deployment knobs (no separate ``celeryconfig.py``).
"""

import os

from celery import Celery
from celery.signals import setup_logging

# Default to local settings so a bare ``celery -A base worker`` works in
# dev without exporting DJANGO_SETTINGS_MODULE.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')

app = Celery('base')

# Pull every CELERY_* setting from Django settings.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover ``tasks.py`` (or ``tasks/`` packages) inside every INSTALLED_APPS
# entry. Feature-level task modules sit at e.g.
# ``client/features/security/onboarding/tasks/purge.py`` and are picked up
# automatically when their app config exposes them.
app.autodiscover_tasks()


@setup_logging.connect
def _route_celery_logging_through_django(**_kwargs):
    """Make Celery use Django's ``LOGGING`` instead of installing its own.

    Without this hook Celery clobbers the dictConfig set up in
    ``base/settings/base.py`` and the ``app.tasks`` logger ends up either
    duplicated (root + custom) or routed through the default Celery
    handler that bypasses our rotating files. Re-applying ``dictConfig``
    here keeps a single source of truth.
    """
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
    from platform.features.support.ops.live_logs.infrastructure.stream_attach import (
        attach_live_log_handlers,
    )

    attach_live_log_handlers()
