"""Start Celery Beat (RedBeat) for the base scheduled tasks.

Usage:
    python manage.py runbeat
    python manage.py runbeat -- -l debug

Requires Redis (``docker compose up -d redis``). Schedules come from
``CELERY_BEAT_SCHEDULE`` (see ``core/tasks/schedules.py``).
"""

import os
import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Start Celery Beat with RedBeat so scheduled tasks are enqueued '
        'on time. Requires Redis up; pair with ``runworkers``.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'celery_args',
            nargs='*',
            help='Extra arguments forwarded to ``celery beat``.',
        )

    def handle(self, *args, **options):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')

        cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'base',
            'beat',
            '-l', 'info',
            '--scheduler', 'core.tasks.scheduler.BaseRedBeatScheduler',
            *options['celery_args'],
        ]
        self.stdout.write(self.style.MIGRATE_HEADING(' '.join(cmd)))
        raise SystemExit(subprocess.call(cmd))
