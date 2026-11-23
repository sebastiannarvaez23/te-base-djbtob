from django.urls import path, include
from platform.features.company.tenant.company.presentation.api import (
    CompanyListCreateAPIView,
    CompanyDetailAPIView,
    CompanyByIdAPIView,
    CompanyCloseAPIView,
    CompanyReopenAPIView,
    CompanyLegalHoldAPIView,
    CompanyExportAPIView,
    CompanyPurgeAPIView,
    CompanySelfCloseAPIView,
    CompanySelfCloseCompleteAPIView,
    CompanyToggleActiveAPIView,
)

urlpatterns = [
    path('', CompanyListCreateAPIView.as_view()),
    path('users/', include('platform.features.company.tenant.users.presentation.urls')),
    path('id/<uuid:company_id>/close/complete/', CompanySelfCloseCompleteAPIView.as_view()),
    path('id/<uuid:company_id>/close/', CompanySelfCloseAPIView.as_view()),
    path('id/<uuid:company_id>/', CompanyByIdAPIView.as_view()),
    path('<uuid:company_id>/toggle-active/', CompanyToggleActiveAPIView.as_view()),
    path('<uuid:company_id>/close/', CompanyCloseAPIView.as_view()),
    path('<uuid:company_id>/reopen/', CompanyReopenAPIView.as_view()),
    path('<uuid:company_id>/legal-hold/', CompanyLegalHoldAPIView.as_view()),
    path('<uuid:company_id>/export/', CompanyExportAPIView.as_view()),
    path('<uuid:company_id>/purge/', CompanyPurgeAPIView.as_view()),
    path('<str:nitcompany>/', CompanyDetailAPIView.as_view()),
]
