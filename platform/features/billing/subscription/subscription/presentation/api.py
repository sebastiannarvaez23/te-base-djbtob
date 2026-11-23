from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.access.decorators import track_usage
from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.permissions import HasSubscriptionAccess, IsCompanyMember, company_for_request
from core.access.billing_recovery import get_request_access_mode
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.subscription.subscription.models import Subscription
from platform.features.billing.subscription.subscription.application.retry_suspended_payment import (
    RetrySuspendedPaymentUseCase,
)
from platform.features.billing.subscription.subscription.application.use_cases import (
    CancelSubscriptionUseCase,
    CreateSubscriptionUseCase,
    DeleteSubscriptionUseCase,
    GetAllSubscriptionsUseCase,
    GetAnnualDiscountUseCase,
    GetSubscriptionChangeStatusUseCase,
    ReactivateSubscriptionUseCase,
    UpdateAnnualDiscountUseCase,
    UpdateSubscriptionUseCase,
)
from platform.features.billing.subscription.subscription.application.change_subscription import ChangeSubscriptionUseCase
from platform.features.billing.subscription.subscription.domain.schemas import (
    CreateSubscriptionSchema,
    RetrySuspendedPaymentInputSchema,
    UpdateSubscriptionSchema,
)
from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository
from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
from platform.features.billing.commerce.payments.infrastructure.routing.router import DefaultPaymentRouter
from platform.features.billing.commerce.payments.integration.adapters.country_currency_policy import (
    DjangoCountryCurrencyPolicy,
)
from platform.features.billing.subscription.subscription.presentation.bodies import (
    CreateSubscriptionBody,
    RetryPaymentBody,
    UpdateAnnualDiscountBody,
    UpdateSubscriptionBody,
    UpgradeSubscriptionBody,
)
from platform.features.billing.subscription.subscription.presentation.queries import (
    CatalogServiceListQuery,
    SubscriptionListQuery,
)


class SubscriptionViewSet(viewsets.ModelViewSet):
    """CRUD of subscription plans."""

    queryset = Subscription.objects.all()
    permission_classes = [HasSubscriptionAccess]
    subscription_functionality = {
        'list': 'settings.subscription.view',
    }

    def _get_repository(self):
        return DjangoSubscriptionRepository()

    @validated_query(SubscriptionListQuery)
    def list(self, request, *args, query: PaginatedQuery, **kwargs):
        subscriptions = GetAllSubscriptionsUseCase(self._get_repository()).execute(
            filters=query.filters,
        )
        dumped = [s.model_dump() for s in subscriptions]
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

    @validated_body(CreateSubscriptionBody)
    def create(self, request, *args, body: dict, **kwargs):
        schema = CreateSubscriptionSchema(**body)
        result = CreateSubscriptionUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'Subscription', result.id, 'CREATE', f'Subscription plan created: {result.name}')
        return wrap_response(result.model_dump(), status_code=201, message="The item has been created successfully.")

    @validated_body(UpdateSubscriptionBody)
    def update(self, request, *args, body: dict, **kwargs):
        schema = UpdateSubscriptionSchema(**body)
        result = UpdateSubscriptionUseCase(self._get_repository()).execute(kwargs.get('pk'), schema)
        if not result:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND, override_detail='Subscription not found.')
        audit_log(request, 'Subscription', kwargs.get('pk'), 'UPDATE', changes = body)
        return wrap_response(result.model_dump())

    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        deleted = DeleteSubscriptionUseCase(self._get_repository()).execute(pk)
        if not deleted:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND, override_detail='Subscription not found.')
        audit_log(request, 'Subscription', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class CatalogServiceOptionsView(APIView):
    """One page of Neurana catalog services the admin can link to a plan."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CatalogServiceListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        from platform.features.billing.subscription.subscription.infrastructure.neurana_catalog import (
            fetch_catalog_page,
        )

        filters = query.filters or {}
        page = fetch_catalog_page(
            page=query.page,
            page_size=query.page_size,
            q=filters.get('q') or '',
            is_active=filters.get('is_active') if 'is_active' in filters else None,
            service_id=filters.get('id') or '',
        )
        if page is None:
            raise ValidationAppException(AppErrorCode.SUB_CATALOG_UNAVAILABLE)
        return wrap_response(page)


class AnnualDiscountView(APIView):
    """Platform parameter: percent off a yearly purchase (12 × monthly)."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoSubscriptionRepository()

    def get(self, request, *args, **kwargs):
        result = GetAnnualDiscountUseCase(self._get_repository()).execute()
        return wrap_response(result.model_dump())

    @validated_body(UpdateAnnualDiscountBody)
    def put(self, request, *args, body: dict, **kwargs):
        result = UpdateAnnualDiscountUseCase(self._get_repository()).execute(
            body['annual_discount_percent'],
        )
        audit_log(
            request, 'BillingSettings', 'annual-discount', 'UPDATE',
            changes=body,
        )
        return wrap_response(result.model_dump())


def _company_id(request):
    """Prefer the JWT company so these views work on the public URLconf too."""
    company = company_for_request(request)
    if company is not None:
        return company.id
    return request.tenant.id


class UpgradeView(APIView):
    """Change the active subscription plan for the current tenant company."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.upgrade'

    @track_usage('settings.subscription.upgrade')
    @validated_body(UpgradeSubscriptionBody)
    def post(self, request, *args, body: dict, **kwargs):

        raw_method = body.get('payment_method_id') or None
        company_id = _company_id(request)

        use_case = ChangeSubscriptionUseCase(
            subscription_repo=DjangoSubscriptionRepository(),
            charge_use_case=CreateChargeUseCase(
                DjangoChargeRepository(),
                DefaultPaymentRouter(),
                currency_policy=DjangoCountryCurrencyPolicy(),
            ),
        )
        result = use_case.execute(
            company_id=company_id,
            subscription_id=body['subscription_id'],
            payment_method_id=raw_method,
            billing_interval=body.get('billing_interval'),
        )
        if not result:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND, override_detail='Subscription not found.')
        audit_log(request, 'CompanySubscription', company_id, 'CHANGE',
                  f'Changed to subscription_id={body["subscription_id"]}')
        return wrap_response(result.model_dump(), status_code=201, message="The item has been created successfully.")


class CancelView(APIView):
    """Cancel the active subscription for the current tenant."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.cancel'

    @track_usage('settings.subscription.cancel')
    def post(self, request, *args, **kwargs):
        company_id = _company_id(request)
        result = CancelSubscriptionUseCase(DjangoSubscriptionRepository()).execute(
            company_id=company_id,
        )
        if not result:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='There is no active subscription to cancel.',
            )
        audit_log(request, 'CompanySubscription', company_id, 'CANCEL')
        return wrap_response(result.model_dump())


class SubscriptionChangeStatusView(APIView):
    """GET — whether the company can change plan, and the change in flight
    (a pending downgrade), for the settings UI."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.view'

    def get(self, request, *args, **kwargs):
        status_data = GetSubscriptionChangeStatusUseCase(DjangoSubscriptionRepository()).execute(
            company_id=_company_id(request),
        )
        return wrap_response(status_data)


class ReactivateView(APIView):
    """Reactivate the most recent cancelled subscription if not yet expired."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def post(self, request, *args, **kwargs):
        company_id = _company_id(request)
        result = ReactivateSubscriptionUseCase(DjangoSubscriptionRepository()).execute(
            company_id=company_id,
        )
        if not result:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='There is no cancelled subscription that can be reactivated.',
            )
        audit_log(request, 'CompanySubscription', company_id, 'REACTIVATE')
        return wrap_response(result.model_dump())


class RetryPaymentView(APIView):
    """Charge again after a suspension for failed renewal (billing recovery)."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_body(RetryPaymentBody)
    def post(self, request, *args, body: dict, **kwargs):
        company_id = _company_id(request)
        result = RetrySuspendedPaymentUseCase(
            repo=DjangoSubscriptionRepository(),
            charge_use_case=CreateChargeUseCase(
                DjangoChargeRepository(),
                DefaultPaymentRouter(),
                currency_policy=DjangoCountryCurrencyPolicy(),
            ),
        ).execute(
            RetrySuspendedPaymentInputSchema(
                company_id=company_id,
                payment_method_id=body.get('payment_method_id'),
                access_mode=get_request_access_mode(request),
            ),
            actor_user=request.user,
        )
        audit_log(request, 'CompanySubscription', company_id, 'BILLING_RECOVERY',
                  'Payment retry succeeded; subscription restored.')
        return wrap_response({
            **result.model_dump(mode='json'),
            'access_restored': True,
        })
