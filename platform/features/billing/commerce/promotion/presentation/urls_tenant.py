from django.urls import path

from .api import (
    TenantActiveBenefitsView,
    TenantRedeemVoucherView,
    TenantValidateVoucherView,
)
from .public_api import PublicPurchaseCheckoutView, PublicPurchasePreviewView

urlpatterns = [
    path('validate/', TenantValidateVoucherView.as_view()),
    path('redeem/', TenantRedeemVoucherView.as_view()),
    path('benefits/', TenantActiveBenefitsView.as_view()),
    path('public/purchase/preview/', PublicPurchasePreviewView.as_view()),
    path('public/purchase/checkout/', PublicPurchaseCheckoutView.as_view()),
]
