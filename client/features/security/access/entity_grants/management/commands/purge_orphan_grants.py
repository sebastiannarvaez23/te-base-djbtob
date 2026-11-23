from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, schema_context

from client.features.security.access.entity_grants.domain.schemas import entity_type_key
from client.features.security.access.entity_grants.presentation import dependencies as deps


class Command(BaseCommand):
    help = (
        'Removes access grants of users who left the company or of records that no longer exist. '
        'Inactive users keep their grants. Use --schema for one tenant or --all for every tenant.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--schema', type=str, help='Tenant schema to run on.')
        parser.add_argument('--all', action='store_true', dest='all_tenants', help='Run on every tenant.')
        parser.add_argument('--dry-run', action='store_true', help='Only report the orphan grants.')

    def handle(self, *args, **options):
        tenants = get_tenant_model().objects.exclude(schema_name='public')
        if options['all_tenants']:
            selected = list(tenants.values_list('id', 'schema_name'))
        elif options['schema']:
            selected = list(tenants.filter(schema_name=options['schema']).values_list('id', 'schema_name'))
            if not selected:
                raise CommandError(f"Unknown tenant schema '{options['schema']}'.")
        else:
            raise CommandError('Use --schema <name> or --all.')
        for company_id, schema in selected:
            self.stdout.write(self.style.MIGRATE_HEADING(f'Tenant: {schema}'))
            with schema_context(schema):
                results = deps.purge_orphan_grants().execute(company_id, dry_run=options['dry_run'])
            self._report(results, options['dry_run'])

    def _report(self, results, dry_run: bool) -> None:
        for result in results:
            label = entity_type_key(result.entity_type)
            if not result.found:
                self.stdout.write(f'  = {label}: no orphan grants')
                continue
            summary = f'{len(result.missing_users)} users, {len(result.missing_entities)} records'
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  ! {label}: orphans for {summary} [dry run]'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  - {label}: deleted {result.deleted} grants ({summary})'))
