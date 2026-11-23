from django.urls import path

from platform.features.configuration.landing.landing.presentation.api import (
    LandingSectionListView,
    LandingSectionToggleView,
)

urlpatterns = [
    path('', LandingSectionListView.as_view(), name='platform-landing-sections'),
    path(
        '<slug:key>/',
        LandingSectionToggleView.as_view(),
        name='platform-landing-section-toggle',
    ),
]
