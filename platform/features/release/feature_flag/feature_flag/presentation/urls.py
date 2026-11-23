from django.urls import path

from platform.features.release.feature_flag.feature_flag.presentation.api import (
    FeatureFlagDetailView,
    FeatureFlagListCreateView,
    FeatureFlagStatusView,
    FeatureFlagToggleView,
)

urlpatterns = [
    path('', FeatureFlagListCreateView.as_view()),
    path('<uuid:pk>/', FeatureFlagDetailView.as_view()),
    path('<uuid:pk>/toggle/', FeatureFlagToggleView.as_view()),
    path('<uuid:pk>/status/', FeatureFlagStatusView.as_view()),
]
