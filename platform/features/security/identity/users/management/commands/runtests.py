"""Management command that delegates to pytest via the venv interpreter.

Usage:
    python manage.py runtests              # run all tests
    python manage.py runtests -- -k auth   # pass extra flags to pytest
"""
import os
import sys
import subprocess

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the test suite using pytest from the project venv.'

    def add_arguments(self, parser):
        parser.add_argument(
            'pytest_args',
            nargs='*',
            help='Extra arguments forwarded to pytest (use -- to separate).',
        )

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))  # manage.py dir
        venv_python = os.path.join(base_dir, 'venv', 'Scripts', 'python.exe')

        if not os.path.isfile(venv_python):
            # Fallback for Linux / macOS
            venv_python = os.path.join(base_dir, 'venv', 'bin', 'python')

        if not os.path.isfile(venv_python):
            self.stderr.write(self.style.ERROR(
                f'venv interpreter not found at {venv_python}'
            ))
            sys.exit(1)

        cmd = [venv_python, '-m', 'pytest'] + options['pytest_args']
        self.stdout.write(self.style.MIGRATE_HEADING(' '.join(cmd)))
        result = subprocess.run(cmd, cwd=base_dir)
        sys.exit(result.returncode)
