from django.urls import path

from platform.features.compliance.policy.policy.presentation.client_api import (
    ClientMyPolicySignaturesView,
    ClientPendingPoliciesView,
    ClientPolicyCountryContentView,
    ClientPublishedPolicyByCodeView,
    ClientSignPolicyView,
    ClientVerifyPolicySignatureView,
)

urlpatterns = [
    path('pending/', ClientPendingPoliciesView.as_view()),
    path('code/<str:code>/', ClientPublishedPolicyByCodeView.as_view()),
    path('signatures/<uuid:signature_id>/verify/', ClientVerifyPolicySignatureView.as_view()),
    path('<uuid:pk>/sign/', ClientSignPolicyView.as_view()),
    path('<uuid:pk>/signatures/me/', ClientMyPolicySignaturesView.as_view()),
    path('<uuid:pk>/countries/<str:country>/', ClientPolicyCountryContentView.as_view()),
]
