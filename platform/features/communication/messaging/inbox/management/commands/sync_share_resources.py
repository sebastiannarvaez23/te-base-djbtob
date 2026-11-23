from django.core.management.base import BaseCommand

from platform.features.communication.messaging.inbox.models import NotificationResourceType
from platform.features.communication.messaging.inbox.resource_catalog import (
    SHAREABLE_RESOURCES,
    sync_shareable_resources,
)


class Command(BaseCommand):
    help = (
        'Sincroniza los tipos de recurso compartibles (campanita) desde el '
        'catálogo de código hacia notification_resource_types.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista el catálogo sin escribir.',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            for entry in SHAREABLE_RESOURCES:
                self.stdout.write(f"  {entry['code']}  {entry['route_template']}")
            self.stdout.write(self.style.WARNING('Dry run: no se escribió nada.'))
            return

        created, updated = sync_shareable_resources(NotificationResourceType)
        self.stdout.write(self.style.SUCCESS(
            f'Share resource types synced. created={created} updated={updated}',
        ))
