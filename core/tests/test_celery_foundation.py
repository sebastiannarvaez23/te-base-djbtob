"""Smoke tests for the Celery foundation.

These don't run a real worker or broker. They guarantee:

  * The Celery app boots from Django settings without import-time
    surprises (cyclic imports, missing settings keys, etc.).
  * Critical reliability settings (ack-late, json serializer, prefetch=1)
    haven't been silently downgraded by a settings refactor.
  * Tasks declared via ``@shared_task(name=...)`` are discoverable —
    a regression here would silently disable Beat schedules whose
    ``task`` field references those names.
  * The ``BEAT_SCHEDULE`` constants reference real registered tasks.

The tests intentionally avoid touching Redis or running tasks; that
class of integration is for a real worker harness (deferred).
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase

from core.tasks.app import app as celery_app
from core.tasks.schedules import build_beat_schedule


class TestCeleryApp(SimpleTestCase):

    def test_app_is_named_after_project(self):
        """``-A base worker`` looks up ``base.celery_app``; the app's main
        name is what shows up in Flower / logs / queue keys."""
        self.assertEqual(celery_app.main, 'base')

    def test_broker_url_comes_from_settings(self):
        """The broker URL must be read from Django settings (not
        hardcoded), so deploys can swap Redis instances per environment
        without code changes."""
        self.assertTrue(celery_app.conf.broker_url)
        self.assertEqual(
            celery_app.conf.broker_url, dj_settings.CELERY_BROKER_URL,
        )

    def test_serializer_is_json_not_pickle(self):
        """Pickle serialisation is an RCE vector: a compromised broker
        can ship arbitrary Python objects to workers. Lock to JSON."""
        self.assertEqual(celery_app.conf.task_serializer, 'json')
        self.assertIn('json', celery_app.conf.accept_content)
        self.assertNotIn('pickle', celery_app.conf.accept_content)

    def test_ack_late_with_prefetch_one(self):
        """At-least-once delivery requires ``acks_late=True`` (so a
        worker crash redelivers the message). Prefetch=1 prevents one
        worker from greedily reserving tasks while it processes a
        slow one. Together they're the reliability baseline."""
        self.assertTrue(celery_app.conf.task_acks_late)
        self.assertEqual(celery_app.conf.worker_prefetch_multiplier, 1)

    def test_beat_scheduler_recovers_lost_redbeat_lock(self):
        """Upstream RedBeat exits on LockNotOwnedError. Local Beat must
        keep running after Windows sleep / Redis TTL expiry."""
        self.assertEqual(
            celery_app.conf.beat_scheduler,
            'core.tasks.scheduler.BaseRedBeatScheduler',
        )

    def test_soft_limit_is_below_hard_limit(self):
        """Soft must trigger before hard, otherwise SoftTimeLimitExceeded
        is unreachable. Off-by-one mistakes here turn timeout handling
        into silent kills."""
        soft = celery_app.conf.task_soft_time_limit
        hard = celery_app.conf.task_time_limit
        self.assertIsNotNone(soft)
        self.assertIsNotNone(hard)
        self.assertLess(soft, hard)


class TestTaskDiscovery(SimpleTestCase):
    """Tasks register at import time via the ``@shared_task`` decorator;
    Celery's autodiscover walks INSTALLED_APPS for a ``tasks`` module/
    package. We force a discovery pass and assert the names we actually
    schedule are present."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Autodiscover is lazy — force the import pass so task names
        # are populated regardless of test ordering.
        celery_app.loader.import_default_modules()

    def test_purge_expired_task_is_registered(self):
        self.assertIn('onboarding.purge_expired', celery_app.tasks)

    def test_beat_schedule_references_existing_tasks(self):
        """A Beat entry whose ``task`` doesn't match any registered
        task fails silently in production — Beat dispatches and the
        message gets dead-lettered. Catching it here is the cheapest
        place."""
        for entry_name, entry in build_beat_schedule().items():
            self.assertIn(
                entry['task'], celery_app.tasks,
                msg=f'BEAT_SCHEDULE entry {entry_name!r} references unknown task',
            )
