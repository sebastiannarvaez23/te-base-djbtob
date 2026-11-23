from django.urls import path

from platform.features.configuration.admin_parameters.admin_parameter.presentation.api import (
    AdminParameterDetailView,
    AdminParameterListCreateView,
)

urlpatterns = [
    path('', AdminParameterListCreateView.as_view()),
    path('<uuid:pk>/', AdminParameterDetailView.as_view()),
]
