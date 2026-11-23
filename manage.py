#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Neurana (el ERP padre) ocupa el 8000. Los backends de producto van en 81xx.
    # Daphne hereda este valor cuando se arranca con `runserver` sin puerto.
    from django.core.management.commands.runserver import Command as Runserver
    Runserver.default_port = '8100'
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
