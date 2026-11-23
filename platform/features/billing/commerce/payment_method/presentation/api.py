from rest_framework import viewsets, status
from rest_framework.response import Response

from core.access.decorators import track_usage, untrack_usage
from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.features.billing.commerce.payment_method.models import PaymentMethod
from platform.features.billing.commerce.payment_method.presentation.bodies import (
    CreatePaymentMethodBody,
    UpdatePaymentMethodBody,
)
from platform.features.billing.commerce.payment_method.presentation.queries import PaymentMethodListQuery
from platform.features.billing.commerce.payment_method.application.use_cases import (
    GetPaymentMethodsByCompanyUseCase,
    CreatePaymentMethodUseCase,
    UpdatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
)
from platform.features.billing.commerce.payment_method.domain.schemas import CreatePaymentMethodSchema, UpdatePaymentMethodSchema
from platform.features.billing.commerce.payment_method.infrastructure.repositories import DjangoPaymentMethodRepository


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """Payment method view set."""

    queryset = PaymentMethod.objects.all()
    permission_classes = [HasSubscriptionAccess]
    subscription_functionality = {
        'list':           'settings.payment-methods.view',
        'create':         'settings.payment-methods.create',
        'partial_update': 'settings.payment-methods.edit',
        'update':         'settings.payment-methods.edit',
        'destroy':        'settings.payment-methods.delete',
    }

    def get_subscription_functionality(self, request):
        """Distingue toggle (solo is_active) de edición general."""
        action = getattr(self, 'action', None)
        if action in ('partial_update', 'update'):
            fields = set(request.data.keys())
            if fields == {'is_active'} or fields == {'is_active', 'company'}:
                return 'settings.payment-methods.toggle'
        return self.subscription_functionality.get(action)

    def _get_repository(self):
        return DjangoPaymentMethodRepository()

    @validated_query(PaymentMethodListQuery)
    def list(self, request, *args, query: PaginatedQuery, **kwargs):
        result = GetPaymentMethodsByCompanyUseCase(self._get_repository()).execute(
            request.tenant.id, query,
        )
        items = [pm.model_dump() for pm in result.items]
        if query.unpaginated:
            return wrap_response(items)
        return wrap_response({
            'items': items,
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_query(PaymentMethodListQuery)
    def list_by_company(self, request, *args, query: PaginatedQuery, **kwargs):
        company_id = kwargs.get('company_id')
        result = GetPaymentMethodsByCompanyUseCase(self._get_repository()).execute(company_id, query)
        items = [pm.model_dump() for pm in result.items]
        if query.unpaginated:
            return wrap_response(items)
        return wrap_response({
            'items': items,
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @track_usage('settings.payment-methods.create')
    @validated_body(CreatePaymentMethodBody)
    def create(self, request, *args, body: dict, **kwargs):
        validated = body
        schema = CreatePaymentMethodSchema(
            company_id=request.tenant.id,
            name=validated.get('name', ''),
            provider=validated.get('provider', ''),
            holder=validated.get('holder', ''),
            last4=validated.get('last4', ''),
            expiry=validated.get('expiry', ''),
            is_active=validated.get('is_active', True),
        )
        result = CreatePaymentMethodUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'PaymentMethod', result.id, 'CREATE', f'Payment method created: {schema.provider} ***{schema.last4}')
        return wrap_response(result.model_dump(), status_code=201, message="The item has been created successfully.")

    @track_usage('settings.payment-methods.edit')
    @validated_body(UpdatePaymentMethodBody)
    def partial_update(self, request, *args, body: dict, **kwargs):
        validated = body
        schema = UpdatePaymentMethodSchema(
            name=validated.get('name'),
            provider=validated.get('provider'),
            holder=validated.get('holder'),
            last4=validated.get('last4'),
            expiry=validated.get('expiry'),
            is_active=validated.get('is_active'),
        )
        pk = kwargs.get('pk')
        result = UpdatePaymentMethodUseCase(self._get_repository()).execute(pk, schema)
        if not result:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND, override_detail='Payment method not found.')
        audit_log(request, 'PaymentMethod', pk, 'UPDATE', changes={k: v for k, v in validated.items() if v is not None})
        return wrap_response(result.model_dump())

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @untrack_usage('settings.payment-methods.create')
    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        deleted = DeletePaymentMethodUseCase(self._get_repository()).execute(pk)
        if not deleted:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND, override_detail='Payment method not found.')
        audit_log(request, 'PaymentMethod', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
