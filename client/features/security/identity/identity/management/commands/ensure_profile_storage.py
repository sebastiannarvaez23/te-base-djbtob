from django.core.management.base import BaseCommand

from client.features.security.identity.identity.infrastructure.profile_storage import ensure_profile_storage


class Command(BaseCommand):
    help = (
        'Ensure the base MinIO bucket has public-read policy for profile pictures '
        'and upload the default avatar (client/assets/profile/avatar.png) if missing.'
    )

    def handle(self, *args, **options):
        ensure_profile_storage()
        self.stdout.write(self.style.SUCCESS('Profile storage ready.'))
