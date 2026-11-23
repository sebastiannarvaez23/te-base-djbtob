import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.email.config import get_email_service
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.communication.email.email_template.application.use_cases import (
    CreateEmailTemplateUseCase,
    DeleteEmailTemplateUseCase,
    GetAllEmailTemplatesUseCase,
    GetEmailTemplateByIdUseCase,
    SendEmailUseCase,
    UpdateEmailTemplateUseCase,
)
from platform.features.communication.email.email_template.domain.schemas import (
    CreateEmailTemplateSchema,
    SendEmailSchema,
    UpdateEmailTemplateSchema,
)
from platform.features.communication.email.email_sender.infrastructure.repositories import DjangoEmailSenderRepository
from platform.features.communication.email.email_template.infrastructure.repositories import DjangoEmailTemplateRepository
from platform.features.communication.email.email_template.presentation.bodies import (
    CreateEmailTemplateBody,
    SendEmailBody,
    UpdateEmailTemplateBody,
)
from platform.features.communication.email.email_template.presentation.queries import (
    EmailTemplateListQuery,
)


def _repo():
    return DjangoEmailTemplateRepository()


def _email_service():
    return get_email_service()


def _catalog_response(query, items):
    dumped = [item.model_dump(mode='json') for item in items]
    if query.unpaginated:
        return wrap_response(dumped)
    total = len(dumped)
    page_items = dumped[query.offset: query.offset + query.page_size]
    return wrap_response({
        'items': page_items,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 1,
    })


# ── CRUD views ────────────────────────────────────────────────────────────────


class EmailTemplateListCreateView(APIView):
    """List all email templates or create a new one."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(EmailTemplateListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = GetAllEmailTemplatesUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, items)

    @validated_body(CreateEmailTemplateBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateEmailTemplateSchema(**body)
        result = CreateEmailTemplateUseCase(_repo()).execute(schema)
        audit_log(
            request, 'EmailTemplate', result.id, 'CREATE',
            f'Email template created: {result.code}',
        )
        return wrap_response(
            result.model_dump(),
            status_code=201,
            message='The email template has been created successfully.',
        )


class EmailTemplateDetailView(APIView):
    """Retrieve, update or delete a single email template."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: uuid.UUID, *args, **kwargs):
        result = GetEmailTemplateByIdUseCase(_repo()).execute(pk)
        if not result:
            raise NotFoundException(
                AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
                override_detail='Email template not found.',
            )
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateEmailTemplateBody)
    def patch(self, request, pk: uuid.UUID, *args, body: dict, **kwargs):
        schema = UpdateEmailTemplateSchema(**body)
        result = UpdateEmailTemplateUseCase(_repo()).execute(pk, schema)
        if not result:
            raise NotFoundException(
                AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
                override_detail='Email template not found.',
            )
        audit_log(
            request, 'EmailTemplate', pk, 'UPDATE',
            changes = body,
        )
        return wrap_response(result.model_dump())

    def delete(self, request, pk: uuid.UUID, *args, **kwargs):
        deleted = DeleteEmailTemplateUseCase(_repo()).execute(pk)
        if not deleted:
            raise NotFoundException(
                AppErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
                override_detail='Email template not found.',
            )
        audit_log(request, 'EmailTemplate', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Send email view ──────────────────────────────────────────────────────────


class SendEmailView(APIView):
    """Send an email using a registered template."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(SendEmailBody)
    def post(self, request, *args, body: dict, **kwargs):
        body = dict(body)
        schema = SendEmailSchema(**body)
        sent = SendEmailUseCase(_repo(), DjangoEmailSenderRepository(), _email_service()).execute(schema)
        return wrap_response(
            {'sent': sent},
            status_code=200,
            message='Email sent successfully.' if sent else 'Email sending failed.',
        )
