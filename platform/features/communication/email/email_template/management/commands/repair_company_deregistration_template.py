"""Repair COMPANY_DEREGISTRATION HTML so email clients can render the header.

Does not seed a missing row. Updates html_template of the existing template
(no migration). SVG/gradient-only headers are replaced with the email-safe
canonical markup used by WELCOME_USER.
"""

from django.core.management.base import BaseCommand

from platform.features.communication.email.email_template.application.company_deregistration_template import (
    HTML_TEMPLATE,
    TEMPLATE_CODE,
)
from platform.features.communication.email.email_template.models import EmailTemplate


class Command(BaseCommand):
    help = (
        'Update COMPANY_DEREGISTRATION html_template to email-safe markup '
        '(no SVG; solid header bgcolor; Django variables on one line).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show whether the stored HTML would change without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            template = EmailTemplate.objects.get(code=TEMPLATE_CODE)
        except EmailTemplate.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f'Template {TEMPLATE_CODE} does not exist; nothing to repair.'
            ))
            return

        if template.html_template.strip() == HTML_TEMPLATE.strip():
            self.stdout.write(self.style.SUCCESS(
                f'{TEMPLATE_CODE} html_template is already email-safe.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'{TEMPLATE_CODE} html_template would be replaced '
                f'({len(template.html_template)} → {len(HTML_TEMPLATE)} chars).'
            ))
            return

        template.html_template = HTML_TEMPLATE
        template.save(update_fields=['html_template', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(
            f'Updated {TEMPLATE_CODE} html_template to email-safe markup.'
        ))
