from django.core.management.base import BaseCommand

from platform.features.configuration.landing.landing.application.use_cases import (
    EnsureLandingSectionsUseCase,
)
from platform.features.configuration.landing.landing.infrastructure.repositories import (
    DjangoLandingSectionRepository,
)


class Command(BaseCommand):
    help = (
        'Ensure all catalog landing sections exist in the public schema. '
        'Does not reset visibility unless --reset-visibility is passed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-visibility',
            action='store_true',
            help='Force every section to is_visible=True.',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if options['dry_run']:
            from platform.features.configuration.landing.landing.domain.catalog import (
                LANDING_SECTION_CATALOG,
            )
            for defn in LANDING_SECTION_CATALOG:
                self.stdout.write(f"would ensure {defn['key']}")
            return

        count = EnsureLandingSectionsUseCase(
            DjangoLandingSectionRepository(),
        ).execute(reset_visibility=options['reset_visibility'])
        self.stdout.write(self.style.SUCCESS(
            f'Landing sections ensured ({count} created/updated).',
        ))
