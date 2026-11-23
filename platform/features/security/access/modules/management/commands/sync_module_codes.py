from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from core.module_codes import admin_module_catalog_index, module_catalog_index
from platform.features.billing.subscription.subscription.models import SubscriptionModule
from platform.features.security.access.roles.models import AdminRoleModule


class Command(BaseCommand):
    help = (
        'Reconcilia module_code en suscripciones y roles tenant (security_modules) y '
        'admin_role_modules (admin_modules) con el casing del catálogo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra cambios sin escribir en la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog = module_catalog_index()
        admin_catalog = admin_module_catalog_index()
        if not catalog and not admin_catalog:
            self.stdout.write(self.style.WARNING('Catálogo de módulos vacío; nada que sincronizar.'))
            return

        updated = 0
        if catalog:
            updated += self._sync_subscription_modules(catalog, dry_run)
            updated += self._sync_tenant_role_modules(catalog, dry_run)
        if admin_catalog:
            updated += self._sync_admin_role_modules(admin_catalog, dry_run)

        label = 'simulados' if dry_run else 'aplicados'
        self.stdout.write(self.style.SUCCESS(f'Listo: {updated} cambio(s) {label}.'))

    def _sync_subscription_modules(self, catalog: dict[str, str], dry_run: bool) -> int:
        count = 0
        for row in SubscriptionModule.objects.all().iterator():
            canonical = catalog.get((row.module_code or '').lower())
            if not canonical or row.module_code == canonical:
                continue
            self.stdout.write(
                f'  subscription_module: {row.subscription_id} {row.module_code!r} -> {canonical!r}'
            )
            if not dry_run:
                row.module_code = canonical
                row.save(update_fields=['module_code'])
            count += 1
        return count

    def _sync_admin_role_modules(self, catalog: dict[str, str], dry_run: bool) -> int:
        count = 0
        for row in AdminRoleModule.objects.all().iterator():
            canonical = catalog.get((row.module_code or '').lower())
            if not canonical or row.module_code == canonical:
                continue
            self.stdout.write(
                f'  admin_role_module: rol={row.rol_id} {row.module_code!r} -> {canonical!r}'
            )
            if not dry_run:
                row.module_code = canonical
                row.save(update_fields=['module_code'])
            count += 1
        return count

    def _sync_tenant_role_modules(self, catalog: dict[str, str], dry_run: bool) -> int:
        from client.features.security.lifecycle.registration.models import RolModule

        count = 0
        Tenant = get_tenant_model()
        for tenant in Tenant.objects.exclude(schema_name='public').iterator():
            with schema_context(tenant.schema_name):
                for row in RolModule.objects.all().iterator():
                    canonical = catalog.get((row.module_code or '').lower())
                    if not canonical or row.module_code == canonical:
                        continue
                    self.stdout.write(
                        f'  [{tenant.schema_name}] rol_module: rol={row.rol_id} '
                        f'{row.module_code!r} -> {canonical!r}'
                    )
                    if not dry_run:
                        row.module_code = canonical
                        row.save(update_fields=['module_code'])
                    count += 1
        return count
