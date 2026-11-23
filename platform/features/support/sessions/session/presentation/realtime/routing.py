from django.urls import path

from platform.features.support.sessions.session.presentation.realtime.consumer import (
    AdminSupportSessionConsumer,
    ClientSupportSessionConsumer,
)

websocket_urlpatterns = [
    path('ws/support/sessions/', ClientSupportSessionConsumer.as_asgi()),
    path('ws/platform/support/sessions/', AdminSupportSessionConsumer.as_asgi()),
]
