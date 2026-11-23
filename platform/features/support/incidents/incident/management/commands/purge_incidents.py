"""
Management command para purgar incidencias en estado terminal.

Uso:
    python manage.py purge_incidents                # usa INCIDENT_RETENTION_DAYS
    python manage.py purge_incidents --days 90
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from platform.features.support.incidents.incident.application.purge_incidents import (
    PurgeIncidentsUseCase,
)
from platform.features.support.incidents.incident.infrastructure.attachment_storage import (
    MinioIncidentAttachmentStorage,
)
from platform.features.support.incidents.incident.infrastructure.repositories import (
    DjangoIncidentRepository,
)

logger = logging.getLogger('app.tasks')


class Command(BaseCommand):
    help = 'Elimina incidencias resueltas/cerradas/descartadas más viejas que la retención.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=None,
            help='Días de retención. Por defecto, INCIDENT_RETENTION_DAYS.',
        )

    def handle(self, *args, **options):
        days = options['days'] or int(getattr(settings, 'INCIDENT_RETENTION_DAYS', 180))
        repo = DjangoIncidentRepository()
        deleted = PurgeIncidentsUseCase(
            repo, attachments=repo, storage=MinioIncidentAttachmentStorage(),
        ).execute(days)
        logger.info('INCIDENT_PURGE deleted=%d retention_days=%d', deleted, days)
        self.stdout.write(self.style.SUCCESS(
            f'Incidencias purgadas: {deleted} (retención {days} días)'))
