from django.core.management.base import BaseCommand

from platform.features.configuration.landing.testimonial.domain.schemas import (
    TestimonialPromptSettingsSchema,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialPromptSettingsRepository,
)
from platform.features.security.catalog_order import next_order
from platform.features.security.access.roles.models import AdminModule, AdminSection

_CODE = 'CRM'
_ROUTE = '/admin/crm'
_ICON = 'bx-conversation'


class Command(BaseCommand):
    help = (
        'Ensure the CRM admin module exists and points to /admin/crm. '
        'Does not seed testimonials.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self._ensure_prompt_settings(dry_run)
        existing = AdminModule.objects.filter(code__iexact=_CODE).first()
        if existing:
            self._update_existing(existing, dry_run)
            return

        section = (
            AdminSection.objects.filter(code__iexact='commercial', is_active=True).first()
            or AdminSection.objects.filter(code__iexact='platform', is_active=True).first()
        )
        if section is None:
            self.stderr.write(self.style.ERROR(
                'No commercial/platform admin section found. Create the catalog section first.',
            ))
            return

        order = next_order(AdminModule, section_id=section.id)
        if dry_run:
            self.stdout.write(
                f'would create {_CODE} under {section.code} order={order} route={_ROUTE}',
            )
            return

        AdminModule.objects.create(
            code=_CODE,
            name='CRM',
            description='Testimonials and related customer feedback.',
            icon=_ICON,
            route=_ROUTE,
            section=section,
            order=order,
            is_sidebar=True,
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f'CRM module created under {section.code}.',
        ))

    def _update_existing(self, existing: AdminModule, dry_run: bool) -> None:
        fields: list[str] = []
        if existing.route != _ROUTE:
            existing.route = _ROUTE
            fields.append('route')
        if not existing.is_sidebar:
            existing.is_sidebar = True
            fields.append('is_sidebar')
        if not existing.is_active:
            existing.is_active = True
            fields.append('is_active')
        if not fields:
            self.stdout.write(f'CRM module already exists ({existing.route}).')
            return
        if dry_run:
            self.stdout.write(f'would update CRM {", ".join(fields)}')
            return
        existing.save(update_fields=fields + ['updated_at'])
        self.stdout.write(self.style.SUCCESS(
            f'CRM module updated ({", ".join(fields)}).',
        ))

    def _ensure_prompt_settings(self, dry_run: bool) -> None:
        repo = DjangoTestimonialPromptSettingsRepository()
        if repo.get() is not None:
            return
        if dry_run:
            self.stdout.write('would create default testimonial prompt settings')
            return
        repo.save(TestimonialPromptSettingsSchema())
        self.stdout.write(self.style.SUCCESS(
            'Default testimonial prompt settings created.',
        ))
