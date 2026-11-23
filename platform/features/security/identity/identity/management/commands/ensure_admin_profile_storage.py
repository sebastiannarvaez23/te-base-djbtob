from django.core.management.base import BaseCommand

from platform.features.security.identity.identity.infrastructure.profile_storage import ensure_profile_storage


class Command(BaseCommand):
    help = (
        'Ensure the base MinIO bucket has public-read policy for admin profile pictures '
        'and upload the default avatar (admin/assets/profile/avatar.png) if missing.'
    )

    def handle(self, *args, **options):
        ensure_profile_storage()
        self.stdout.write(self.style.SUCCESS('Admin profile storage ready.'))
