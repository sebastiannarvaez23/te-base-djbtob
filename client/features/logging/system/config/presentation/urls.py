from django.urls import path

from client.features.logging.system.config.presentation.api import LogConfigDetailAPIView, LogConfigListAPIView

urlpatterns = [
    path('', LogConfigListAPIView.as_view(), name='log-config-list'),
    path('<str:log_type>/', LogConfigDetailAPIView.as_view(), name='log-config-detail'),
]
