"""Django project package.

The ``celery_app`` re-export is the standard Celery discovery hook —
``celery -A base worker`` looks up ``base.celery_app`` to find the
configured application. The actual configuration lives in
``core.tasks.app``; ``base/celery.py`` is just a re-export shim.
"""

from base.celery import app as celery_app

__all__ = ['celery_app']
