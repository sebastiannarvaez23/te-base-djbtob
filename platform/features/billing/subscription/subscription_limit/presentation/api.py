from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.subscription.subscription_limit.application.use_cases import (
    CreateSubscriptionLimitUseCase,
    DeleteSubscriptionLimitUseCase,
    GetAllSubscriptionLimitsUseCase,
    GetSubscriptionLimitByIdUseCase,
    GetSubscriptionLimitsBySubscriptionUseCase,
    UpdateSubscriptionLimitUseCase,
)
from platform.features.billing.subscription.subscription_limit.domain.schemas import (
    CreateSubscriptionLimitSchema,
    UpdateSubscriptionLimitSchema,
)
from platform.features.billing.subscription.subscription_limit.infrastructure.repositories import DjangoSubscriptionLimitRepository
from platform.features.billing.subscription.subscription_limit.presentation.bodies import (
    CreateSubscriptionLimitBody,
    UpdateSubscriptionLimitBody,
)
from platform.features.billing.subscription.subscription_limit.presentation.queries import (
    SubscriptionLimitBySubscriptionQuery,
    SubscriptionLimitListQuery,
)


def _repo():
    return DjangoSubscriptionLimitRepository()


def _catalog_response(query, items):
    dumped = [l.model_dump() for l in items]
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


class SubscriptionLimitListCreateView(APIView):
    """List all subscription limits or create a new one."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SubscriptionLimitListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        limits = GetAllSubscriptionLimitsUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, limits)

    @validated_body(CreateSubscriptionLimitBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateSubscriptionLimitSchema(
            subscription_id=body['subscription'],
            functionality_id=body['functionality'],
            name=body.get('name', ''),
            max_value=body['max_value'],
            validation_type=body.get('validation_type', 'lifetime'),
            window_hours=body.get('window_hours'),
        )
        result = CreateSubscriptionLimitUseCase(_repo()).execute(schema)
        audit_log(request, 'SubscriptionLimit', result.id, 'CREATE',
                  f'Tope creado: {result.functionality_key} = {result.max_value} en {result.subscription_name}')
        return wrap_response(result.model_dump(), status_code=201, message='The item has been created successfully.')


class SubscriptionLimitBySubscriptionView(APIView):
    """List all limits for a given subscription."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SubscriptionLimitBySubscriptionQuery)
    def get(self, request, subscription_id, *args, query: PaginatedQuery, **kwargs):
        limits = GetSubscriptionLimitsBySubscriptionUseCase(_repo()).execute(
            subscription_id, filters=query.filters,
        )
        return _catalog_response(query, limits)


class SubscriptionLimitDetailView(APIView):
    """Retrieve, update or delete a single subscription limit."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetSubscriptionLimitByIdUseCase(_repo()).execute(pk)
        if not result:
            raise NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND,
                                    override_detail='Subscription limit not found.')
        return wrap_response(result.model_dump())

    @validated_body(UpdateSubscriptionLimitBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateSubscriptionLimitSchema(**body)
        result = UpdateSubscriptionLimitUseCase(_repo()).execute(pk, schema)
        if not result:
            raise NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND,
                                    override_detail='Subscription limit not found.')
        audit_log(request, 'SubscriptionLimit', pk, 'UPDATE', changes = body)
        return wrap_response(result.model_dump())

    def delete(self, request, pk, *args, **kwargs):
        deleted = DeleteSubscriptionLimitUseCase(_repo()).execute(pk)
        if not deleted:
            raise NotFoundException(AppErrorCode.SLIMIT_NOT_FOUND,
                                    override_detail='Subscription limit not found.')
        audit_log(request, 'SubscriptionLimit', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
