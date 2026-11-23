from django.urls import path

from .api import ModelRoutingSettingsView

urlpatterns = [
    path('', ModelRoutingSettingsView.as_view(), name='platform-ai-model-routing'),
]
