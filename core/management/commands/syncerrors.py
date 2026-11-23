"""
Sincroniza el catálogo de errores del backend hacia los frontends.

Uso:
    python manage.py syncerrors
    python manage.py syncerrors --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from core.errors.sync_i18n import SyncErrorsError, sync_error_i18n


class Command(BaseCommand):
    help = (
        'Sincroniza ERROR_REGISTRY (core.errors.codes) hacia errors.json '
        'en base-client-web y base-admin-web (en/es). Valida que message/detail '
        'del backend estén en inglés y que existan traducciones ES.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Valida el catálogo sin escribir archivos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            result = sync_error_i18n(dry_run=dry_run)
        except SyncErrorsError as exc:
            raise CommandError(str(exc)) from exc

        action = 'validated' if dry_run else 'wrote'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {result.code_count} error codes'
        ))
        for path in result.written_paths:
            prefix = 'would write' if dry_run else 'wrote'
            self.stdout.write(f'  {prefix}: {path}')
