"""Celery discovery shim.

Standard Celery convention is to expose the application object at
``<project>/celery.py``; the real configuration lives in
``core.tasks.app`` because Celery is cross-cutting infrastructure that
sits at the same level as ``core.audit`` and ``core.errors``.

Anything that imports ``base.celery_app`` (Celery's CLI, ``base/__init__``,
test fixtures) gets the same instance.
"""

from core.tasks.app import app  # noqa: F401  — re-export

__all__ = ['app']
