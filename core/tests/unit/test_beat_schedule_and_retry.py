"""Unit tests for Beat schedule and BaseTask retry policy."""

from __future__ import annotations

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

import pytest
from celery.schedules import crontab
from django.db import OperationalError

from core.tasks.base import BaseTask, RetryableTaskError
from core.tasks.schedules import build_beat_schedule

pytestmark = pytest.mark.unit


class BuildBeatScheduleTests(TestCase):

    def test_core_maintenance_entries_always_present(self):
        schedule = build_beat_schedule()
        self.assertIn('onboarding-purge-expired-daily', schedule)
        self.assertIn('subscription-renew-due-daily', schedule)
        self.assertIn('invoice-reconcile-fiscal-pending-daily', schedule)
        purge = schedule['onboarding-purge-expired-daily']
        self.assertEqual(purge['task'], 'onboarding.purge_expired')
        self.assertEqual(
            schedule['invoice-reconcile-fiscal-pending-daily']['task'],
            'invoice.reconcile_fiscal_pending',
        )
        self.assertIsInstance(purge['schedule'], crontab)

    def test_demo_probe_is_not_scheduled(self):
        schedule = build_beat_schedule()
        self.assertNotIn('task-monitor-demo-probe-every-2m', schedule)
        self.assertNotIn('task_monitor.demo_probe', {
            entry['task'] for entry in schedule.values()
        })

    def test_fiscal_relay_interval_comes_from_caller(self):
        schedule = build_beat_schedule(fiscal_relay_interval=15.0)
        self.assertEqual(schedule['billing-fiscal-outbox-relay']['schedule'], 15.0)


class BaseTaskRetryPolicyTests(TestCase):

    def test_autoretry_includes_transient_and_retryable_domain_errors(self):
        self.assertIn(ConnectionError, BaseTask.autoretry_for)
        self.assertIn(TimeoutError, BaseTask.autoretry_for)
        self.assertIn(OperationalError, BaseTask.autoretry_for)
        self.assertIn(RetryableTaskError, BaseTask.autoretry_for)

    def test_retry_backoff_and_max_retries(self):
        self.assertTrue(BaseTask.retry_backoff)
        self.assertEqual(BaseTask.max_retries, 5)
        self.assertEqual(BaseTask.retry_backoff_max, 600)
        self.assertTrue(BaseTask.retry_jitter)

    def test_retryable_task_error_is_distinct_exception(self):
        with self.assertRaises(RetryableTaskError):
            raise RetryableTaskError('try again')
