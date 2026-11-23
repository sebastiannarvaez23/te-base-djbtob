from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from client.features.security.lifecycle.registration.feature_registry import FEATURE_REGISTRY
from client.features.security.lifecycle.registration.models import Rol, RolFeature
from platform.features.security.access.functionalities.models import Functionality
from platform.features.security.access.modules.models import Module


# Roles que deben tener acceso a TODAS las funcionalidades del sistema.
ADMIN_ROLE_NAMES = {'Administrator'}


class Command(BaseCommand):
    help = (
        'Sincroniza el catálogo de features desde el registry de código hacia la base de datos. '
        'Crea las features que no existen, actualiza label y category de las existentes, '
        'y desactiva las que ya no están en el registry. '
        'Además asigna automáticamente todas las features al rol Administrator. '
        'Usa --schema para ejecutarlo en un tenant específico, o --all para todos los tenants.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los cambios que se realizarían sin aplicarlos.',
        )
        parser.add_argument(
            '--schema',
            type=str,
            help='Esquema del tenant donde ejecutar la sincronización.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            dest='all_tenants',
            help='Ejecutar en todos los tenants.',
        )
        parser.add_argument(
            '--skip-admin-assign',
            action='store_true',
            help='Omitir la asignación automática de features al rol Administrator.',
        )

    def handle(self, *args, **options):
        target_schema = options.get('schema')
        all_tenants = options.get('all_tenants')

        if all_tenants:
            TenantModel = get_tenant_model()
            for tenant in TenantModel.objects.exclude(schema_name='public'):
                self.stdout.write(self.style.MIGRATE_HEADING(f'\nTenant: {tenant.schema_name}'))
                with schema_context(tenant.schema_name):
                    self._sync(options)
            return

        if target_schema:
            self.stdout.write(self.style.MIGRATE_HEADING(f'\nTenant: {target_schema}'))
            with schema_context(target_schema):
                self._sync(options)
            return

        self._sync(options)

    def _sync(self, options):
        dry_run = options['dry_run']
        skip_admin = options.get('skip_admin_assign', False)
        registry_keys = {entry['key'] for entry in FEATURE_REGISTRY}

        created = updated = deactivated = 0

        module_cache: dict = {}

        for entry in FEATURE_REGISTRY:
            module_code = entry['module']
            if module_code not in module_cache:
                module = Module.objects.filter(code__iexact=module_code).first()
                if module is None:
                    self.stdout.write(self.style.WARNING(f'  ! Module not found: {module_code}, skipping {entry["key"]}'))
                    continue
                module_cache[module_code] = module

            module_obj = module_cache[module_code]
            feature, was_created = Functionality.objects.get_or_create(
                key=entry['key'],
                defaults={
                    'module':    module_obj,
                    'label':     entry['label'],
                    'category':  entry['category'],
                    'is_active': True,
                },
            )

            if was_created:
                created += 1
                self.stdout.write(f'  + {entry["key"]}')
                if dry_run:
                    feature.delete()
            else:
                changed = False
                if feature.module_id != module_obj.id:
                    if not dry_run:
                        feature.module = module_obj
                    changed = True
                for field in ('label', 'category'):
                    if getattr(feature, field) != entry[field]:
                        if not dry_run:
                            setattr(feature, field, entry[field])
                        changed = True
                if not feature.is_active:
                    if not dry_run:
                        feature.is_active = True
                    changed = True
                if changed:
                    updated += 1
                    self.stdout.write(f'  ~ {entry["key"]}')
                    if not dry_run:
                        feature.save(update_fields=['module', 'label', 'category', 'is_active'])

        # Desactivar features que ya no están en el registry
        orphans = Functionality.objects.filter(is_active=True).exclude(key__in=registry_keys)
        for orphan in orphans:
            deactivated += 1
            self.stdout.write(self.style.WARNING(f'  - {orphan.key} (desactivada)'))
            if not dry_run:
                orphan.is_active = False
                orphan.save(update_fields=['is_active'])

        suffix = ' [DRY RUN]' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\nFeatures sincronizadas{suffix}: '
            f'{created} creadas, {updated} actualizadas, {deactivated} desactivadas.'
        ))

        if not dry_run:
            try:
                from client.features.logging.facade.factory import LogManagerFactory
                from client.features.logging.facade.context import LogContextBuilder
                from client.features.logging.system.system.domain.schemas import SystemLogSchema

                ctx = LogContextBuilder.from_system('sync_features')
                LogManagerFactory.create().system(ctx, SystemLogSchema(
                    component='sync_features',
                    message=f'Features synced: {created} created, {updated} updated, {deactivated} deactivated',
                    level='INFO',
                ))
            except Exception:
                pass

        # Asignar TODAS las features activas a los roles admin
        if not skip_admin and not dry_run:
            self._assign_all_to_admin_roles()

    def _assign_all_to_admin_roles(self):
        all_features = list(Functionality.objects.filter(is_active=True))
        admin_roles = Rol.objects.filter(name__in=ADMIN_ROLE_NAMES, company_id__isnull=True)

        assigned_count = 0
        for rol in admin_roles:
            existing_ids = set(
                RolFeature.objects.filter(rol=rol).values_list('feature_id', flat=True)
            )
            new_entries = [
                RolFeature(rol=rol, feature=f)
                for f in all_features
                if f.id not in existing_ids
            ]
            if new_entries:
                RolFeature.objects.bulk_create(new_entries, ignore_conflicts=True)
                assigned_count += len(new_entries)
                self.stdout.write(
                    f'  -> {rol.name}: {len(new_entries)} feature(s) nuevas asignadas'
                )

        if assigned_count == 0:
            self.stdout.write('  -> Administrator: todas las features ya estaban asignadas.')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nAdmin roles actualizados: {assigned_count} asignaciones nuevas.'
            ))
