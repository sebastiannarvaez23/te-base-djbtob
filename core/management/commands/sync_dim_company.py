from __future__ import annotations

from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from core.analytics.infrastructure.postgres_store import PostgresAnalyticsStore


class Command(BaseCommand):
    help = (
        'Upsert dw.dim_company from public Company rows '
        '(excludes the public tenant schema).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Also sync CLOSED / PENDING_PURGE / GONE companies as is_active=false.',
        )

    def handle(self, *args, **options):
        from platform.features.company.tenant.company.models import Company, CompanyLifecycle

        public_schema = getattr(settings, 'PUBLIC_SCHEMA_NAME', 'public')
        qs = Company.objects.exclude(schema_name=public_schema)
        if not options['include_inactive']:
            qs = qs.filter(lifecycle=CompanyLifecycle.ACTIVE)

        rows = []
        now = datetime.now(timezone.utc)
        for company in qs.iterator():
            rows.append({
                'company_id': company.id,
                'schema_name': company.schema_name,
                'name': company.name,
                'nit': company.nit or '',
                'lifecycle': company.lifecycle,
                'is_active': company.lifecycle == CompanyLifecycle.ACTIVE,
                'loaded_at': now,
            })

        if not rows:
            self.stdout.write('No companies to sync.')
            return

        store = PostgresAnalyticsStore()
        written = store.upsert_dimension(
            'dim_company',
            rows,
            company_id=rows[0]['company_id'],
        )
        self.stdout.write(self.style.SUCCESS(f'Synced {written} dim_company rows.'))
