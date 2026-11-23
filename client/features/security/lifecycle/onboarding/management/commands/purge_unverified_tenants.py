"""Manual entry-point for the unverified-tenants sweep.

Companion to ``purge_expired_onboardings``: this one targets *finalised*
registrations whose admin user never confirmed their email and that
remain inert in the database. Defaults to a 7-day retention so users on
holiday don't lose their tenants prematurely.

The actual sweep logic lives in
:class:`client.features.security.lifecycle.onboarding.application.use_cases
.purge_unverified_tenants.PurgeUnverifiedTenantsUseCase`.
"""

import logging

from django.core.management.base import BaseCommand

from client.features.security.lifecycle.onboarding.application.use_cases.purge_unverified_tenants import (
    PurgeUnverifiedTenantsUseCase,
)


logger = logging.getLogger('app.api')


class Command(BaseCommand):
    help = (
        'Delete Companies whose entire user population has never confirmed '
        'their email and were created more than --retention-days ago.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-days', type=int, default=7,
            help='Tenants younger than this are kept regardless (default: 7).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report counts without deleting anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        result = PurgeUnverifiedTenantsUseCase(
            retention_days=options['retention_days'],
        ).execute(dry_run=dry_run)

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}tenants_deleted={result.tenants_deleted} '
            f'users_deleted={result.users_deleted}'
        ))
        logger.info(
            'purge_unverified_tenants complete',
            extra={
                'dry_run': dry_run,
                'tenants_deleted': result.tenants_deleted,
                'users_deleted': result.users_deleted,
            },
        )
