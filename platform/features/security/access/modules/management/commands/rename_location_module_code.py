"""Rename catalog module LOCATION/location → WAREHOUSE and remap module filters."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from core.module_codes import rename_module_code_in_grants
from platform.features.security.access.modules.models import Module

OLD_CODES = ('location', 'LOCATION')
NEW_CODE = 'WAREHOUSE'
OLD_FILTER_KEY = 'location'
NEW_FILTER_KEY = 'warehouse'


class Command(BaseCommand):
    help = (
        'Renombra el módulo de catálogo location/LOCATION a WAREHOUSE, '
        'propaga grants/suscripciones y remapea module_filters tenant.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra cambios sin escribir en la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = 0

        for old in OLD_CODES:
            qs = Module.objects.filter(code=old)
            count = qs.count()
            if not count:
                continue
            self.stdout.write(f'  Module.code: {old!r} -> {NEW_CODE!r} ({count})')
            if not dry_run:
                qs.update(code=NEW_CODE)
                rename_module_code_in_grants(old, NEW_CODE)
            updated += count

        # Si el código ya es WAREHOUSE pero grants siguen con LOCATION/location.
        if Module.objects.filter(code=NEW_CODE).exists():
            for old in OLD_CODES:
                if not dry_run:
                    rename_module_code_in_grants(old, NEW_CODE)

        updated += self._remap_module_filters(dry_run)

        label = 'simulados' if dry_run else 'aplicados'
        self.stdout.write(self.style.SUCCESS(f'Listo: {updated} cambio(s) {label}.'))
        if not dry_run:
            self.stdout.write(
                'Siguiente: python manage.py sync_module_codes && python manage.py sync_features'
            )

    def _remap_module_filters(self, dry_run: bool) -> int:
        from client.features.security.identity.module_filters.models import ModuleFilter

        count = 0
        Tenant = get_tenant_model()
        for tenant in Tenant.objects.exclude(schema_name='public').iterator():
            with schema_context(tenant.schema_name):
                qs = ModuleFilter.objects.filter(module_key=OLD_FILTER_KEY)
                n = qs.count()
                if not n:
                    continue
                self.stdout.write(
                    f'  [{tenant.schema_name}] module_filters: '
                    f'{OLD_FILTER_KEY!r} -> {NEW_FILTER_KEY!r} ({n})'
                )
                if not dry_run:
                    qs.update(module_key=NEW_FILTER_KEY)
                count += n
        return count
