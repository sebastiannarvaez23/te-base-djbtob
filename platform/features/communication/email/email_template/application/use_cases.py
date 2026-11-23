import uuid
import logging
from typing import List, Optional
from django.template import Template, Context

from core.email.domain.interfaces import IEmailService
from core.email.domain.schemas import SendEmailMessage
from core.errors import NotFoundException, ConflictException, AppErrorCode, ServerException
from ...email_sender.domain.interfaces import IEmailSenderRepository
from ..domain.interfaces import IEmailTemplateRepository
from .template_source import normalize_django_template_source
from ..domain.schemas import (
    CreateEmailTemplateSchema,
    EmailTemplateSchema,
    SendEmailSchema,
    UpdateEmailTemplateSchema,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class GetAllEmailTemplatesUseCase:
    def __init__(self, repository: IEmailTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[EmailTemplateSchema]:
        return self.repository.get_all(filters=filters)


class GetEmailTemplateByIdUseCase:
    def __init__(self, repository: IEmailTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> Optional[EmailTemplateSchema]:
        return self.repository.get_by_id(id)


class CreateEmailTemplateUseCase:
    def __init__(self, repository: IEmailTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateEmailTemplateSchema) -> EmailTemplateSchema:
        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.EMAIL_DUPLICATE_CODE,
                override_detail=f"An email template with code '{data.code}' already exists.",
            )
        return self.repository.create(data)


class UpdateEmailTemplateUseCase:
    def __init__(self, repository: IEmailTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateEmailTemplateSchema) -> Optional[EmailTemplateSchema]:
        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.EMAIL_DUPLICATE_CODE,
                    override_detail=f"An email template with code '{data.code}' already exists.",
                )
        return self.repository.update(id, data)


class DeleteEmailTemplateUseCase:
    def __init__(self, repository: IEmailTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)


class SendEmailUseCase:
    """Resolve a template by code, render it with context, and send."""

    def __init__(
        self,
        repository: IEmailTemplateRepository,
        sender_repository: IEmailSenderRepository,
        email_service: IEmailService,
    ):
        self.repository = repository
        self.sender_repository = sender_repository
        self.email_service = email_service

    @trace_layer('application')
    def execute(self, data: SendEmailSchema) -> bool:
        template = self.repository.get_by_code(data.template_code)
        if not template:
            raise NotFoundException(
                AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
                override_detail=f"Email template with code '{data.template_code}' not found.",
            )

        if not template.is_active:
            raise ConflictException(
                AppErrorCode.EMAIL_TEMPLATE_INACTIVE,
                override_detail=f"Email template '{data.template_code}' is inactive.",
            )

        # Production sends use ONLY the caller's data-layer context.
        # ``mock_data`` is reserved for admin preview/emulation — never merge
        # it into real deliveries or sample values (Carlos Rodríguez, etc.)
        # leak when a key is missing from the context.
        render_context = dict(data.context or {})

        # Render subject and HTML template with the data-layer context.
        # Collapse pretty-printed {{ tags }} before Django's lexer runs.
        try:
            rendered_subject = Template(
                normalize_django_template_source(template.subject)
            ).render(Context(render_context))
            rendered_html = Template(
                normalize_django_template_source(template.html_template)
            ).render(Context(render_context))
            rendered_body = (
                Template(normalize_django_template_source(template.body)).render(
                    Context(render_context)
                )
                if template.body
                else ''
            )
        except Exception as exc:
            logger.error(f'Email template render error [{data.template_code}]: {exc}')
            raise ServerException(
                AppErrorCode.EMAIL_RENDER_ERROR,
                override_detail=f"Failed to render email template '{data.template_code}'.",
            )

        # Resolve sender: template FK → default sender → settings fallback
        from_email = ''
        from_name = ''
        reply_to = ''

        if template.sender:
            sender = self.sender_repository.get_by_id(template.sender)
            if sender:
                from_email = sender.email
                from_name = sender.name
                reply_to = sender.reply_to
        else:
            default_sender = self.sender_repository.get_default()
            if default_sender:
                from_email = default_sender.email
                from_name = default_sender.name
                reply_to = default_sender.reply_to

        return self.email_service.send(SendEmailMessage(
            to=data.to,
            subject=rendered_subject,
            html_body=rendered_html,
            plain_body=rendered_body,
            from_email=from_email,
            from_name=from_name,
            cc=data.cc,
            bcc=data.bcc,
            reply_to=reply_to,
            attachments=data.attachments,
        ))
