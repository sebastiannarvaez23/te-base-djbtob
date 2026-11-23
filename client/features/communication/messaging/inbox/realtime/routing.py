"""Rutas WebSocket de la campanita (se agregan al router ASGI en base/asgi.py)."""

from django.urls import path

from client.features.communication.messaging.inbox.realtime.consumer import NotificationConsumer

websocket_urlpatterns = [
    path('ws/client/inbox/', NotificationConsumer.as_asgi()),
]
