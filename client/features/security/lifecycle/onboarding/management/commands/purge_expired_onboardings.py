"""Manual entry-point for the onboarding GC sweep.

Operators run this during incidents or for one-off cleanups. The actual
sweep logic lives in
:class:`client.features.security.lifecycle.onboarding.application.use_cases.purge_expired.PurgeExpiredOnboardingsUseCase`
— this command is just a CLI transport so the same logic stays
reachable when Celery/Beat are unavailable (or before they exist in a
fresh environment).
"""

import logging

from django.core.management.base import BaseCommand

from client.features.security.lifecycle.onboarding.application.use_cases.purge_expired import (
    PurgeExpiredOnboardingsUseCase,
)


logger = logging.getLogger('app.api')


class Command(BaseCommand):
    help = 'Expire abandoned onboarding registrations and purge consumed email-confirmation tokens.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--failed-retention-days', type=int, default=30,
            help='How many days to keep FAILED_PROVISIONING rows before hard-deleting (default: 30).',
        )
        parser.add_argument(
            '--token-retention-days', type=int, default=7,
            help='How many days to keep consumed/expired email-confirmation tokens (default: 7).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report counts without making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        result = PurgeExpiredOnboardingsUseCase(
            failed_retention_days=options['failed_retention_days'],
            token_retention_days=options['token_retention_days'],
        ).execute(dry_run=dry_run)

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}expired={result.expired} '
            f'failed_deleted={result.failed_deleted} '
            f'tokens_deleted={result.tokens_deleted}'
        ))
        logger.info(
            'purge_expired_onboardings complete',
            extra={
                'dry_run':        dry_run,
                'expired':        result.expired,
                'failed_deleted': result.failed_deleted,
                'tokens_deleted': result.tokens_deleted,
            },
        )
