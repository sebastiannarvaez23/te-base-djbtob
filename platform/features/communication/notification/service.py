import logging

from core.email.config import get_email_service
from core.email.domain.interfaces import IEmailService

from platform.features.communication.email.email_sender.infrastructure.repositories import (
    DjangoEmailSenderRepository,
)
from platform.features.communication.email.email_template.application.use_cases import (
    SendEmailUseCase,
)
from platform.features.communication.email.email_template.domain.schemas import SendEmailSchema
from platform.features.communication.email.email_template.infrastructure.repositories import (
    DjangoEmailTemplateRepository,
)
from .interfaces import INotificationService

logger = logging.getLogger('app.api')


class NotificationService(INotificationService):
    """
    Facade that wires up email infrastructure and exposes a simple API
    for any module to dispatch template-based emails.

    Usage:
        from platform.features.communication.notification.service import NotificationService

        NotificationService().send_email(
            template_code='WELCOME_ADMIN',
            to=['admin@example.com'],
            context={'user_name': 'John', 'company_name': 'Acme'},
        )
    """

    def __init__(self, email_service: IEmailService | None = None):
        self._template_repo = DjangoEmailTemplateRepository()
        self._sender_repo = DjangoEmailSenderRepository()
        self._email_service = email_service or get_email_service()

    def send_email(
        self,
        template_code: str,
        to: list[str],
        context: dict,
        attachments: list[dict] | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> bool:
        schema = SendEmailSchema(
            template_code=template_code,
            to=to,
            context=context,
            attachments=attachments or [],
            cc=cc or [],
            bcc=bcc or [],
        )
        use_case = SendEmailUseCase(
            repository=self._template_repo,
            sender_repository=self._sender_repo,
            email_service=self._email_service,
        )
        try:
            return use_case.execute(schema)
        except Exception as exc:
            logger.error(f'Notification dispatch failed [{template_code}]: {exc}')
            return False
