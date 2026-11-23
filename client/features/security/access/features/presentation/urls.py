from django.urls import path

from client.features.security.access.features.presentation.api import (
    FeatureDetailAPIView,
    FeatureListCreateAPIView,
)

urlpatterns = [
    path('', FeatureListCreateAPIView.as_view(), name='company-features'),
    path('<uuid:feature_id>/', FeatureDetailAPIView.as_view(), name='company-feature-detail'),
]
