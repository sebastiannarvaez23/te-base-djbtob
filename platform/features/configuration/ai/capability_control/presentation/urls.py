from django.urls import path

from .api import CapabilityControlView

urlpatterns = [
    path('', CapabilityControlView.as_view(), name='platform-ai-capabilities'),
]
