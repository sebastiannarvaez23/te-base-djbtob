from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.communication.email.email_sender.infrastructure.repositories import DjangoEmailSenderRepository
from platform.features.communication.email.email_sender.application.use_cases import (
    GetAllEmailSendersUseCase, CreateEmailSenderUseCase,
    GetEmailSenderByIdUseCase, UpdateEmailSenderUseCase, DeleteEmailSenderUseCase,
)
from platform.features.communication.email.email_sender.domain.schemas import (
    CreateEmailSenderSchema,
    EmailSenderSchema,
    UpdateEmailSenderSchema,
)
from platform.features.communication.email.email_sender.presentation.bodies import CreateEmailSenderBody, UpdateEmailSenderBody
from platform.features.communication.email.email_sender.presentation.queries import EmailSenderListQuery

repo = DjangoEmailSenderRepository()


def _dump_sender(sender) -> dict:
    return EmailSenderSchema.model_validate(sender).model_dump(mode='json')


def _catalog_response(query, items):
    dumped = [_dump_sender(s) for s in items]
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


class EmailSenderListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(EmailSenderListQuery)
    def get(self, request, *, query: PaginatedQuery):
        senders = GetAllEmailSendersUseCase(repo).execute(filters=query.filters)
        return _catalog_response(query, senders)

    @validated_body(CreateEmailSenderBody)
    def post(self, request, *, body: dict):
        schema = CreateEmailSenderSchema(**body)
        sender = CreateEmailSenderUseCase(repo).execute(schema)
        return wrap_response(_dump_sender(sender), status_code=201)


class EmailSenderDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        sender = GetEmailSenderByIdUseCase(repo).execute(pk)
        return wrap_response(_dump_sender(sender))

    @validated_body(UpdateEmailSenderBody)
    def patch(self, request, pk, *, body: dict):
        schema = UpdateEmailSenderSchema(**body)
        sender = UpdateEmailSenderUseCase(repo).execute(pk, schema)
        return wrap_response(_dump_sender(sender))

    def delete(self, request, pk):
        DeleteEmailSenderUseCase(repo).execute(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
