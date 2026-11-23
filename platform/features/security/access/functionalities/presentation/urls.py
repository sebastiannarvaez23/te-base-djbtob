from django.urls import path

from platform.features.security.access.functionalities.presentation.api import (
    FunctionalityAssignAPIView,
    FunctionalityDetailAPIView,
    FunctionalityListCreateAPIView,
    FunctionalityToggleAPIView,
)

urlpatterns = [
    path('', FunctionalityListCreateAPIView.as_view(), name='functionality-list-create'),
    path('<uuid:functionality_id>/', FunctionalityDetailAPIView.as_view(), name='functionality-detail'),
    path('<uuid:functionality_id>/toggle/', FunctionalityToggleAPIView.as_view(), name='functionality-toggle'),
    path('<uuid:functionality_id>/assign/', FunctionalityAssignAPIView.as_view(), name='functionality-assign'),
]
