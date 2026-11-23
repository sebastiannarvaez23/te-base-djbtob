from django.urls import path
from platform.features.billing.subscription.subscription.presentation.api import (
    AnnualDiscountView,
    CatalogServiceOptionsView,
    SubscriptionViewSet,
)

urlpatterns = [
    path('annual-discount/', AnnualDiscountView.as_view()),
    path('catalog-services/', CatalogServiceOptionsView.as_view()),
    path('', SubscriptionViewSet.as_view({'get': 'list', 'post': 'create'})),
    path(
        '<uuid:pk>/',
        SubscriptionViewSet.as_view({'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}),
    ),
]
