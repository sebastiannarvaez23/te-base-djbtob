from django.urls import path

from platform.features.billing.complement.entitlement.presentation.api import (
    CompanyComplementListCreateView,
    CompanyComplementRevokeView,
    ComplementCatalogView,
)

urlpatterns = [
    path('catalog/', ComplementCatalogView.as_view(), name='complement-catalog'),
    path('companies/<uuid:company_id>/', CompanyComplementListCreateView.as_view(), name='company-complements'),
    path(
        'companies/<uuid:company_id>/<uuid:entitlement_id>/revoke/',
        CompanyComplementRevokeView.as_view(),
        name='company-complement-revoke',
    ),
]
