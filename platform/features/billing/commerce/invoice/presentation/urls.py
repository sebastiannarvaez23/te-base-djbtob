from django.urls import path
from platform.features.billing.commerce.invoice.presentation.api import InvoiceViewSet

urlpatterns = [
    path('', InvoiceViewSet.as_view({'get': 'list_admin', 'post': 'create'})),
    path(
        'company/<uuid:company_id>/',
        InvoiceViewSet.as_view({'get': 'list_by_company'}),
    ),
    path(
        '<str:invoice_number>/',
        InvoiceViewSet.as_view({'get': 'retrieve_by_number'}),
    ),
    path(
        '<uuid:pk>/status/',
        InvoiceViewSet.as_view({'patch': 'update_status'}),
    ),
    path(
        '<uuid:pk>/download/',
        InvoiceViewSet.as_view({'get': 'download'}),
    ),
    path(
        '<uuid:pk>/resend/',
        InvoiceViewSet.as_view({'post': 'resend'}),
    ),
    path(
        '<uuid:pk>/',
        InvoiceViewSet.as_view({'delete': 'destroy'}),
    ),
]
