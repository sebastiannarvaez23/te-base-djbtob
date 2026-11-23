from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.subscription.subscription_functionality.application.use_cases import (
    GetSubscriptionFunctionalitiesUseCase,
    UpdateSubscriptionFunctionalitiesUseCase,
)
from platform.features.billing.subscription.subscription_functionality.domain.schemas import UpdateSubscriptionFunctionalitiesSchema
from platform.features.billing.subscription.subscription_functionality.infrastructure.repositories import DjangoSubscriptionFunctionalityRepository
from platform.features.billing.subscription.subscription_functionality.presentation.bodies import (
    UpdateSubscriptionFunctionalitiesBody,
)
from platform.features.billing.subscription.subscription_functionality.presentation.queries import (
    SubscriptionFunctionalityBySubscriptionQuery,
)


def _repo():
    return DjangoSubscriptionFunctionalityRepository()


def _catalog_response(query, items):
    dumped = [f.model_dump() for f in items]
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


class SubscriptionFunctionalitiesBySubscriptionView(APIView):
    """List all functionalities for a given subscription."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SubscriptionFunctionalityBySubscriptionQuery)
    def get(self, request, subscription_id, *args, query: PaginatedQuery, **kwargs):
        functionalities = GetSubscriptionFunctionalitiesUseCase(_repo()).execute(
            subscription_id, filters=query.filters,
        )
        return _catalog_response(query, functionalities)


class SubscriptionFunctionalitiesUpdateView(APIView):
    """Replace (sync) functionalities for a given subscription."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateSubscriptionFunctionalitiesBody)
    def put(self, request, subscription_id, *args, body: dict, **kwargs):
        schema = UpdateSubscriptionFunctionalitiesSchema(
            functionality_keys = body['functionality_keys'],
        )
        result = UpdateSubscriptionFunctionalitiesUseCase(_repo()).execute(subscription_id, schema)
        if result is None:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='Subscription not found.',
            )
        audit_log(request, 'SubscriptionFunctionality', subscription_id, 'UPDATE_FUNCTIONALITIES',
                  changes={'functionality_keys': schema.functionality_keys})
        return wrap_response([f.model_dump() for f in result])
