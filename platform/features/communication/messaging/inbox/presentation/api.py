"""API del administrador (schema público, registrada en urls_public).

Vistas finas: validan el input, instancian repositorio → use case, y
envuelven la respuesta con ``wrap_response``. Sin lógica de negocio.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.communication.messaging.inbox.application.use_cases import (
    ArchiveAdminInboxUseCase,
    CreateAdminNotificationUseCase,
    CreateResourceTypeUseCase,
    GetAdminInboxUnreadCountUseCase,
    ListAdminInboxUseCase,
    ListAdminOutboxUseCase,
    ListResourceTypesUseCase,
    MarkAdminInboxReadUseCase,
    MarkAllAdminInboxReadUseCase,
    UpdateResourceTypeUseCase,
)
from platform.features.communication.messaging.inbox.domain.enums import ReadStatus
from platform.features.communication.messaging.inbox.domain.schemas import (
    AdminNotifyInput,
    Audience,
    CreateResourceTypeSchema,
    UpdateResourceTypeSchema,
)
from platform.features.communication.messaging.inbox.infrastructure.dispatch_trigger import (
    CeleryOutboxDispatchTrigger,
)
from platform.features.communication.messaging.inbox.infrastructure.repositories import (
    DjangoAdminInboxRepository,
    DjangoOutboxRepository,
    DjangoResourceTypeRepository,
)
from platform.features.communication.messaging.inbox.presentation.queries import (
    AdminInboxQuery,
    OutboxQuery,
    ResourceTypeListQuery,
)
from platform.features.communication.messaging.inbox.presentation.bodies import (
    AdminNotifyBody,
    ResourceTypeCreateBody,
    ResourceTypeUpdateBody,
)


def _admin_label(user) -> str:
    full = f'{getattr(user, "first_name", "")} {getattr(user, "last_name", "")}'.strip()
    return full or getattr(user, 'username', 'Administrador')


# ── Envíos del administrador ──────────────────────────────────────────────────

class AdminNotificationView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _outbox_repo():
        return DjangoOutboxRepository()

    @validated_body(AdminNotifyBody)
    def post(self, request, *args, body: dict, **kwargs):
        vd = body

        body = AdminNotifyInput(
            admin_id=request.user.id,
            admin_label=_admin_label(request.user),
            title=vd['title'],
            body=vd.get('body', ''),
            level=vd['level'],
            audience=Audience(
                scope=vd['scope'],
                target_company_id=vd.get('target_company_id'),
                target_user_id=vd.get('target_user_id'),
            ),
        )
        use_case = CreateAdminNotificationUseCase(
            outbox_repo=self._outbox_repo(),
            dispatch_trigger=CeleryOutboxDispatchTrigger(),
        )
        result = use_case.execute(body)
        audit_log(request, 'AdminNotification', result.id, 'CREATE',
                  f'Admin notification queued: scope={result.scope} title={result.title}')
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='Notification queued for delivery.',
        )

    @validated_query(OutboxQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListAdminOutboxUseCase(self._outbox_repo()).execute(query)
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


# ── Tipos de recurso compartible ──────────────────────────────────────────────

class ResourceTypeView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _repo():
        return DjangoResourceTypeRepository()

    @validated_query(ResourceTypeListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        only_active = bool(query.filters.get('only_active', False))
        result = ListResourceTypesUseCase(self._repo()).execute(only_active=only_active)
        return wrap_response([r.model_dump(mode='json') for r in result])

    @validated_body(ResourceTypeCreateBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateResourceTypeSchema(**body)
        result = CreateResourceTypeUseCase(self._repo()).execute(schema)
        audit_log(request, 'NotificationResourceType', result.id, 'CREATE',
                  f'Resource type created: {result.code}')
        return wrap_response(result.model_dump(mode='json'), status_code=201,
                             message='The item has been created successfully.')


class ResourceTypeDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _repo():
        return DjangoResourceTypeRepository()

    @validated_body(ResourceTypeUpdateBody)
    def patch(self, request, *args, body: dict, **kwargs):
        schema = UpdateResourceTypeSchema(**body)
        result = UpdateResourceTypeUseCase(self._repo()).execute(kwargs.get('code'), schema)
        audit_log(request, 'NotificationResourceType', result.id, 'UPDATE',
                  changes = body)
        return wrap_response(result.model_dump(mode='json'))


def _admin_inbox_repo():
    return DjangoAdminInboxRepository()


class AdminInboxListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AdminInboxQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        status = ReadStatus(query.filters.get('status', ReadStatus.ALL.value))
        items, total = ListAdminInboxUseCase(_admin_inbox_repo()).execute(
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


class AdminInboxUnreadCountView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        count = GetAdminInboxUnreadCountUseCase(_admin_inbox_repo()).execute(request.user.id)
        return wrap_response({'unread_count': count})


class AdminInboxMarkReadView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        affected = MarkAdminInboxReadUseCase(_admin_inbox_repo()).execute(
            request.user.id, kwargs.get('pk'),
        )
        return wrap_response({'updated': affected})


class AdminInboxMarkAllReadView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        affected = MarkAllAdminInboxReadUseCase(_admin_inbox_repo()).execute(request.user.id)
        return wrap_response({'updated': affected})


class AdminInboxArchiveView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        affected = ArchiveAdminInboxUseCase(_admin_inbox_repo()).execute(
            request.user.id, kwargs.get('pk'),
        )
        return wrap_response({'archived': affected})
