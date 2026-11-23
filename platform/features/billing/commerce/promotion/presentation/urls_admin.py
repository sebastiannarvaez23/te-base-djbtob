from django.urls import path

from .api import (
    PromotionRedemptionListView,
    PromotionVoucherBulkCreateView,
    PromotionVoucherDetailView,
    PromotionVoucherListCreateView,
    PromotionVoucherRevokeView,
)

urlpatterns = [
    path('vouchers/', PromotionVoucherListCreateView.as_view()),
    path('vouchers/bulk/', PromotionVoucherBulkCreateView.as_view()),
    path('vouchers/<uuid:pk>/', PromotionVoucherDetailView.as_view()),
    path('vouchers/<uuid:pk>/revoke/', PromotionVoucherRevokeView.as_view()),
    path('redemptions/', PromotionRedemptionListView.as_view()),
]
