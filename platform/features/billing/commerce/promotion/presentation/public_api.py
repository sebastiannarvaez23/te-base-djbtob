from core.decorators.response import wrap_response
from core.validators import validated_body

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.domain.schemas import (
    PublicPurchaseCheckoutSchema,
    PublicPurchasePreviewRequestSchema,
)
from platform.features.billing.commerce.promotion.presentation.bodies import (
    PublicPurchaseCheckoutBody,
    PublicPurchasePreviewBody,
)
from rest_framework.views import APIView


class PublicPurchasePreviewView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(PublicPurchasePreviewBody)
    def post(self, request, *, body: dict):
        data = PublicPurchasePreviewRequestSchema(**body)
        result = composition.build_public_preview_use_case().execute(data)
        return wrap_response(result.model_dump(mode='json'))


class PublicPurchaseCheckoutView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(PublicPurchaseCheckoutBody)
    def post(self, request, *, body: dict):
        data = PublicPurchaseCheckoutSchema(**body)
        result = composition.build_public_checkout_use_case().execute(data)
        return wrap_response(result.model_dump(mode='json'), message='Purchase completed successfully.')
