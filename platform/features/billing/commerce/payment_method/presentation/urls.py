from django.urls import path
from platform.features.billing.commerce.payment_method.presentation.api import PaymentMethodViewSet

urlpatterns = [
    path('', PaymentMethodViewSet.as_view({'get': 'list', 'post': 'create'})),
    path(
        'company/<uuid:company_id>/',
        PaymentMethodViewSet.as_view({'get': 'list_by_company'}),
    ),
    path(
        '<uuid:pk>/',
        PaymentMethodViewSet.as_view({'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}),
    ),
]
