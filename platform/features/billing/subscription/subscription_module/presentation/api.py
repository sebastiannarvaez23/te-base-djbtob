from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.subscription.subscription_module.application.use_cases import (
    GetSubscriptionModulesUseCase,
    UpdateSubscriptionModulesUseCase,
)
from platform.features.billing.subscription.subscription_module.domain.schemas import UpdateSubscriptionModulesSchema
from platform.features.billing.subscription.subscription_module.infrastructure.repositories import DjangoSubscriptionModuleRepository
from platform.features.billing.subscription.subscription_module.presentation.bodies import UpdateSubscriptionModulesBody
from platform.features.billing.subscription.subscription_module.presentation.queries import (
    SubscriptionModuleBySubscriptionQuery,
)


def _repo():
    return DjangoSubscriptionModuleRepository()


def _catalog_response(query, items):
    dumped = [m.model_dump() for m in items]
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


class SubscriptionModulesBySubscriptionView(APIView):
    """List all modules for a given subscription."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SubscriptionModuleBySubscriptionQuery)
    def get(self, request, subscription_id, *args, query: PaginatedQuery, **kwargs):
        modules = GetSubscriptionModulesUseCase(_repo()).execute(
            subscription_id, filters=query.filters,
        )
        return _catalog_response(query, modules)


class SubscriptionModulesUpdateView(APIView):
    """Replace (sync) modules for a given subscription."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateSubscriptionModulesBody)
    def put(self, request, subscription_id, *args, body: dict, **kwargs):
        schema = UpdateSubscriptionModulesSchema(
            module_codes = body['module_codes'],
        )
        result = UpdateSubscriptionModulesUseCase(_repo()).execute(subscription_id, schema)
        if result is None:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='Subscription not found.',
            )
        audit_log(request, 'SubscriptionModule', subscription_id, 'UPDATE_MODULES',
                  changes={'module_codes': schema.module_codes})
        return wrap_response([m.model_dump() for m in result])
