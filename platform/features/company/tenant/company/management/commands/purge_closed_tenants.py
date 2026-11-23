"""Manual entry-point for closed-tenant purge after the grace window."""

import logging

from django.core.management.base import BaseCommand

from platform.features.company.tenant.company.application.purge_company import (
    PurgeClosedCompanyUseCase,
    PurgeDueClosedCompaniesUseCase,
)
from platform.features.company.tenant.company.domain.schemas import PurgeClosedCompanySchema
from platform.features.company.tenant.company.infrastructure.export_store import MinioTenantExportStore
from platform.features.company.tenant.company.infrastructure.offboarding import (
    DjangoCompanyOffboardingRepository,
)


logger = logging.getLogger('app.api')


class Command(BaseCommand):
    help = 'Purge CLOSED companies whose grace window has ended.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report candidates without mutating anything.',
        )
        parser.add_argument(
            '--company-id',
            type=str,
            default='',
            help='Purge a single company instead of the due sweep.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip the grace window (still requires export and no legal hold).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        companies = DjangoCompanyOffboardingRepository()
        store = MinioTenantExportStore()
        company_id = (options.get('company_id') or '').strip()
        if company_id:
            result = PurgeClosedCompanyUseCase(companies, store).execute(
                PurgeClosedCompanySchema(
                    company_id=company_id,
                    force=bool(options.get('force')),
                    dry_run=dry_run,
                ),
            )
            prefix = '[dry-run] ' if dry_run else ''
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}company_id={result.id} lifecycle={result.lifecycle}'
            ))
            return

        result = PurgeDueClosedCompaniesUseCase(companies, store).execute(dry_run=dry_run)
        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}purged={result["purged"]} skipped={result["skipped"]}'
        ))
        logger.info('purge_closed_tenants complete', extra={'dry_run': dry_run, **result})
