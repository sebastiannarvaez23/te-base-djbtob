from django.urls import path

from platform.features.security.access.sections.presentation.api import (
    SectionDetailAPIView,
    SectionListCreateAPIView,
    SectionReorderAPIView,
)

urlpatterns = [
    path('', SectionListCreateAPIView.as_view(), name='platform-sections'),
    path('reorder/', SectionReorderAPIView.as_view(), name='platform-sections-reorder'),
    path('<uuid:section_id>/', SectionDetailAPIView.as_view(), name='platform-section-detail'),
]
