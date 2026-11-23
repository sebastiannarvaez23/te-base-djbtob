from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

from platform.core.authentication import AdminTokenAuthentication

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.application.use_cases import (
    CreateBulkVouchersUseCase,
    CreateVoucherUseCase,
    GetVoucherUseCase,
    ListActiveBenefitsUseCase,
    ListRedemptionsUseCase,
    ListVouchersUseCase,
    RedeemVoucherUseCase,
    RevokeVoucherUseCase,
    ValidateVoucherUseCase,
)
from platform.features.billing.commerce.promotion.domain.schemas import (
    CreateBulkVouchersSchema,
    CreateVoucherSchema,
    RedeemVoucherSchema,
    ValidateVoucherSchema,
)
from platform.features.billing.commerce.promotion.presentation.bodies import (
    CreateBulkVouchersBody,
    CreateVoucherBody,
    RedeemVoucherBody,
    ValidateVoucherBody,
)
from platform.features.billing.commerce.promotion.presentation.queries import (
    RedemptionListQuery,
    TenantBenefitsQuery,
    VoucherQuery,
)


def _repo():
    return composition.get_promotion_repo()


def _dump(model) -> dict:
    return model.model_dump(mode='json')


class PromotionVoucherListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(VoucherQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = dict(query.filters)
        filters['page'] = query.page
        filters['page_size'] = query.page_size
        result = ListVouchersUseCase(_repo()).execute(**filters)
        return wrap_response({
            'items': [_dump(v) for v in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateVoucherBody)
    def post(self, request, *args, body: dict, **kwargs):
        body = CreateVoucherSchema(
            **body,
            created_by_id=getattr(request.user, 'id', None),
        )
        result = CreateVoucherUseCase(
            _repo(), notifier=composition.build_company_voucher_notifier(),
        ).execute(body)
        audit_log(request, 'PromotionVoucher', result.id, 'CREATE', f'Voucher {result.serial}')
        return wrap_response(_dump(result), status_code=201, message='Voucher created successfully.')


class PromotionVoucherBulkCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(CreateBulkVouchersBody)
    def post(self, request, *args, body: dict, **kwargs):
        body = CreateBulkVouchersSchema(
            **body,
            scope='COMPANY',
            created_by_id=getattr(request.user, 'id', None),
        )
        result = CreateBulkVouchersUseCase(_repo()).execute(body)
        audit_log(request, 'PromotionVoucher', None, 'CREATE', f'Bulk vouchers: {result.created}')
        return wrap_response(_dump(result), status_code=201)


class PromotionVoucherDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetVoucherUseCase(_repo()).execute(pk)
        return wrap_response(_dump(result))


class PromotionVoucherRevokeView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        result = RevokeVoucherUseCase(_repo()).execute(pk)
        audit_log(request, 'PromotionVoucher', pk, 'UPDATE', 'Voucher revoked')
        return wrap_response(_dump(result))


class PromotionRedemptionListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(RedemptionListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = {
            'company_id': query.filters.get('company_id') or None,
            'voucher_id': query.filters.get('voucher_id') or None,
        }
        result = ListRedemptionsUseCase(_repo()).execute(**filters)
        return wrap_response([_dump(r) for r in result])


class TenantValidateVoucherView(APIView):
    permission_classes = [HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.apply-voucher'

    @validated_body(ValidateVoucherBody)
    def post(self, request, *args, body: dict, **kwargs):
        payload = dict(body)
        payload['company_id'] = request.tenant.id
        payload['context'] = 'SETTINGS'
        body = ValidateVoucherSchema(**payload)
        result = ValidateVoucherUseCase(_repo(), composition.get_plan_catalog()).execute(body)
        return wrap_response(_dump(result))


class TenantRedeemVoucherView(APIView):
    permission_classes = [HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.apply-voucher'

    @validated_body(RedeemVoucherBody)
    def post(self, request, *args, body: dict, **kwargs):
        payload = dict(body)
        payload['company_id'] = request.tenant.id
        payload['context'] = 'SETTINGS'
        body = RedeemVoucherSchema(**payload)
        result = RedeemVoucherUseCase(
            _repo(), composition.get_plan_catalog(), composition.get_charge_port(),
        ).execute(body)
        audit_log(request, 'PromotionRedemption', result.redemption.id, 'CREATE', result.redemption.voucher_serial)
        return wrap_response(_dump(result), message='Voucher redeemed successfully.')


class TenantActiveBenefitsView(APIView):
    permission_classes = [HasSubscriptionAccess]
    subscription_functionality = 'settings.subscription.view-voucher-applied'

    @validated_query(TenantBenefitsQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        status_filter = query.filters.get('status')
        result = ListActiveBenefitsUseCase(_repo()).execute(
            request.tenant.id, status=status_filter,
        )
        return wrap_response([_dump(b) for b in result])
