from django.urls import path

from platform.features.configuration.admin_parameters.admin_parameter_type.presentation.api import (
    AdminParameterTypeDetailView,
    AdminParameterTypeListCreateView,
)

urlpatterns = [
    path('', AdminParameterTypeListCreateView.as_view()),
    path('<uuid:pk>/', AdminParameterTypeDetailView.as_view()),
]
