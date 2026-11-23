from __future__ import annotations

from datetime import date
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from core.analytics.application.dim_date import iter_dim_date_rows
from core.analytics.infrastructure.postgres_store import PostgresAnalyticsStore


class Command(BaseCommand):
    help = 'Load dw.dim_date for a date range (operational seed; not a migration).'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='date_from', required=True, help='YYYY-MM-DD')
        parser.add_argument('--to', dest='date_to', required=True, help='YYYY-MM-DD')
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Rows per upsert batch (default 500).',
        )

    def handle(self, *args, **options):
        try:
            start = date.fromisoformat(options['date_from'])
            end = date.fromisoformat(options['date_to'])
        except ValueError as exc:
            raise CommandError(f'Invalid date: {exc}') from exc

        rows = iter_dim_date_rows(start, end)
        store = PostgresAnalyticsStore()
        batch_size = max(1, options['batch_size'])
        written = 0
        # dim_date is global; port signature still requires company_id.
        nil = UUID('00000000-0000-0000-0000-000000000000')
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            written += store.upsert_dimension('dim_date', chunk, company_id=nil)

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {written} dim_date rows '
            f'({start.isoformat()} .. {end.isoformat()})',
        ))
