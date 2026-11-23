from django.urls import path
from platform.features.configuration.parameters.parameter.presentation.api import (
    ParameterDetailView,
    ParameterListCreateView,
)

urlpatterns = [
    path('', ParameterListCreateView.as_view()),
    path('<uuid:pk>/', ParameterDetailView.as_view()),
]
