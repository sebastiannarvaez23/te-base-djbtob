from django.conf import settings
from django.core.management.base import BaseCommand

from core.email.domain.headers import parse_from_address

from platform.features.communication.email.email_sender.application.use_cases import (
    CreateEmailSenderUseCase,
    UpdateEmailSenderUseCase,
)
from platform.features.communication.email.email_sender.domain.schemas import (
    CreateEmailSenderSchema,
    UpdateEmailSenderSchema,
)
from platform.features.communication.email.email_sender.infrastructure.repositories import (
    DjangoEmailSenderRepository,
)

PLATFORM_SENDER_CODE = 'PLATFORM'


class Command(BaseCommand):
    help = (
        'Upsert the default platform sender (notificaciones@base.local) '
        'used by templates when no sender is set.'
    )

    def handle(self, *args, **options):
        name = getattr(settings, 'EMAIL_FROM_NAME', 'Notificaciones de la base') or 'Notificaciones de la base'
        email = parse_from_address(getattr(settings, 'DEFAULT_FROM_EMAIL', '')) or 'notificaciones@base.local'
        reply_to = getattr(settings, 'EMAIL_REPLY_TO', '') or 'info@base.local'

        repo = DjangoEmailSenderRepository()
        existing = repo.get_by_code(PLATFORM_SENDER_CODE)
        if existing:
            UpdateEmailSenderUseCase(repo).execute(
                existing.id,
                UpdateEmailSenderSchema(
                    name=name,
                    email=email,
                    reply_to=reply_to,
                    is_default=True,
                    is_active=True,
                ),
            )
            self.stdout.write(self.style.SUCCESS(
                f'Updated sender {PLATFORM_SENDER_CODE}: {name} <{email}>'
            ))
            return

        CreateEmailSenderUseCase(repo).execute(
            CreateEmailSenderSchema(
                code=PLATFORM_SENDER_CODE,
                name=name,
                email=email,
                reply_to=reply_to,
                is_default=True,
                is_active=True,
            )
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created sender {PLATFORM_SENDER_CODE}: {name} <{email}>'
        ))
