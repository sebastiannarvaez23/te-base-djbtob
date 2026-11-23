from django.urls import path
from platform.features.configuration.parameters.parameter_type.presentation.api import (
    ParameterTypeDetailView,
    ParameterTypeListCreateView,
)

urlpatterns = [
    path('', ParameterTypeListCreateView.as_view()),
    path('<uuid:pk>/', ParameterTypeDetailView.as_view()),
]
