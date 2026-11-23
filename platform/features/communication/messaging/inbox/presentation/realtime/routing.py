from django.urls import path

from platform.features.communication.messaging.inbox.presentation.realtime.consumer import (
    AdminInboxConsumer,
)

websocket_urlpatterns = [
    path('ws/platform/inbox/', AdminInboxConsumer.as_asgi()),
]
