"""Crea las features de gobierno del handbook. No va en migraciones."""

from django.core.management.base import BaseCommand

from core.ids import uuid7
from handbook.core.constants import APPROVE_FEATURE_KEY, PROPOSE_FEATURE_KEY
from platform.features.security.access.roles.models import AdminFeature, AdminModule, AdminSection


class Command(BaseCommand):
    help = 'Ensure admin.docs.propose and admin.docs.approve exist.'

    def handle(self, *args, **options):
        section, _ = AdminSection.objects.get_or_create(
            code='platform',
            defaults={'id': uuid7(), 'name': 'Platform', 'order': 0},
        )
        module, _ = AdminModule.objects.get_or_create(
            code='handbook',
            defaults={
                'id': uuid7(),
                'name': 'Handbook',
                'icon': 'bx-book',
                'route': '/handbook',
                'section': section,
                'order': 0,
            },
        )
        for key, label in (
            (PROPOSE_FEATURE_KEY, 'Propose handbook changes'),
            (APPROVE_FEATURE_KEY, 'Approve handbook changes'),
        ):
            AdminFeature.objects.get_or_create(
                key=key,
                defaults={
                    'id': uuid7(),
                    'label': label,
                    'module': module,
                    'category': 'features',
                    'is_active': True,
                },
            )
        self.stdout.write(self.style.SUCCESS('Handbook admin features are ready.'))
