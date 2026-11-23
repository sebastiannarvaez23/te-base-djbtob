"""API de la campanita (usuario de empresa).

Registrada en base/urls.py (host tenant) y base/urls_public.py (SPA host).
En el host público el mixin entra al schema de la empresa del JWT.
"""

from django.db import connection
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .schema import CompanySchemaMixin

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

from client.features.communication.messaging.inbox.application.use_cases import (
    ArchiveNotificationUseCase,
    GetUnreadCountUseCase,
    ListInboxUseCase,
    MarkAllReadUseCase,
    MarkNotificationReadUseCase,
)
from client.features.communication.messaging.inbox.domain.context import NotificationContextBuilder
from client.features.communication.messaging.inbox.domain.enums import ReadStatus
from client.features.communication.messaging.inbox.domain.schemas import ShareInput
from client.features.communication.messaging.inbox.facade.factory import NotificationManagerFactory
from client.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoNotificationRepository,
)
from client.features.communication.messaging.inbox.presentation.queries import InboxQuery
from client.features.communication.messaging.inbox.presentation.bodies import ShareBody


def _repo():
    return DjangoNotificationRepository()


class InboxAPIView(CompanySchemaMixin, APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]


class InboxListView(InboxAPIView):
    """GET api/v1/client/inbox/?status=unread → listado paginado de la campanita."""

    @validated_query(InboxQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        status = ReadStatus(query.filters.get('status', ReadStatus.ALL.value))
        items, total = ListInboxUseCase(_repo()).execute(
            user_id=request.user.id,
            status=status,
            limit=query.limit,
            offset=query.offset,
        )
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in items],
            'total': total,
            'page': query.page,
            'page_size': query.page_size,
            'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 1,
        })


class UnreadCountView(InboxAPIView):
    """GET api/v1/client/inbox/unread-count/ → contador para el badge de la campanita."""

    def get(self, request, *args, **kwargs):
        count = GetUnreadCountUseCase(_repo()).execute(request.user.id)
        return wrap_response({'unread_count': count})


class MarkReadView(InboxAPIView):
    """POST api/v1/client/inbox/<pk>/read/ → marca una notificación como leída."""

    def post(self, request, *args, **kwargs):
        affected = MarkNotificationReadUseCase(_repo()).execute(request.user.id, kwargs.get('pk'))
        return wrap_response({'updated': affected})


class MarkAllReadView(InboxAPIView):
    """POST api/v1/client/inbox/read-all/ → marca todas como leídas."""

    def post(self, request, *args, **kwargs):
        affected = MarkAllReadUseCase(_repo()).execute(request.user.id)
        return wrap_response({'updated': affected})


class ArchiveView(InboxAPIView):
    """POST api/v1/client/inbox/<pk>/archive/ → archiva (oculta) una notificación."""

    def post(self, request, *args, **kwargs):
        affected = ArchiveNotificationUseCase(_repo()).execute(request.user.id, kwargs.get('pk'))
        return wrap_response({'archived': affected})


class ShareView(InboxAPIView):
    """POST api/v1/client/inbox/share/ → comparte un elemento con usuarios de la empresa."""

    @validated_body(ShareBody)
    def post(self, request, *args, body: dict, **kwargs):
        body = ShareInput(**body)

        context = NotificationContextBuilder.from_request(request)
        count = NotificationManagerFactory.create().share(
            context=context,
            data=body,
            schema_name=connection.schema_name,
        )
        audit_log(request, 'Notification', body.resource_id, 'SHARE',
                  f'Shared {body.resource_type_code} with {count} user(s)')
        return wrap_response(
            {'recipients': count},
            status_code=201,
            message='Notification shared successfully.',
        )
