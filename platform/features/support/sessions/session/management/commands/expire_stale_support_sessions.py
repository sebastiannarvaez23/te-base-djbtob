"""
Manual sweeper for timed-out support sessions.

Usage:
    python manage.py expire_stale_support_sessions
"""

from django.core.management.base import BaseCommand

from platform.features.support.sessions.session.application import factory as session_factory


class Command(BaseCommand):
    help = (
        'Cancel QUEUED sessions past the configured wait timeout and close '
        'AWAITING_RATING sessions past the rating TTL.'
    )

    def handle(self, *args, **options):
        result = session_factory.build_expire_stale().execute()
        self.stdout.write(self.style.SUCCESS(
            f"Cancelled queued={result['cancelled_queued']} "
            f"closed awaiting_rating={result['closed_awaiting_rating']}"
        ))
