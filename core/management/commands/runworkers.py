"""Start the Celery worker for the base background tasks.

Usage:
    python manage.py runworkers
    python manage.py runworkers -- -l debug

Named ``runworkers`` (not ``runworker``) because Django Channels already
registers ``runworker`` for the channel-layer consumer.

Requires Redis (``docker compose up -d redis``). Defaults match the
Windows-safe local setup (``--pool=solo --concurrency=1``).
"""

import os
import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Start the Celery worker that executes scheduled and async tasks. '
        'Requires Redis up.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'celery_args',
            nargs='*',
            help='Extra arguments forwarded to ``celery worker``.',
        )

    def handle(self, *args, **options):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')

        cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'base',
            'worker',
            '-l', 'info',
            '--pool=solo',
            '--concurrency=1',
            *options['celery_args'],
        ]
        self.stdout.write(self.style.MIGRATE_HEADING(' '.join(cmd)))
        raise SystemExit(subprocess.call(cmd))
