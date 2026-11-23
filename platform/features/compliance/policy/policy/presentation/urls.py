from django.urls import path

from platform.features.compliance.policy.policy.presentation.api import (
    PendingPoliciesView,
    PolicyCountryDetailView,
    PolicyCountryDraftReleaseView,
    PolicyCountryDraftView,
    PolicyCountryVersionsView,
    PolicyDetailView,
    PolicyListCreateView,
    PolicySignaturesListView,
    SignPolicyView,
    VerifyPolicySignatureView,
)

urlpatterns = [
    path('', PolicyListCreateView.as_view()),
    path('pending/', PendingPoliciesView.as_view()),
    path('signatures/<uuid:signature_id>/verify/', VerifyPolicySignatureView.as_view()),
    path('<uuid:pk>/', PolicyDetailView.as_view()),
    path('<uuid:pk>/sign/', SignPolicyView.as_view()),
    path('<uuid:pk>/signatures/', PolicySignaturesListView.as_view()),
    path('<uuid:pk>/countries/<str:country>/draft/release/', PolicyCountryDraftReleaseView.as_view()),
    path('<uuid:pk>/countries/<str:country>/draft/', PolicyCountryDraftView.as_view()),
    path('<uuid:pk>/countries/<str:country>/versions/', PolicyCountryVersionsView.as_view()),
    path('<uuid:pk>/countries/<str:country>/', PolicyCountryDetailView.as_view()),
]
