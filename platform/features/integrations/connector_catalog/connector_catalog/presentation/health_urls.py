from django.urls import path

from .api import IntegrationHealthView

urlpatterns = [
    path('', IntegrationHealthView.as_view(), name='integration-health'),
]
