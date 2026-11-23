"""Rutas WebSocket del assistant."""

from django.urls import path

from client.features.communication.assistant.chat.realtime.consumer import AssistantChatConsumer

websocket_urlpatterns = [
    path('ws/assistant/', AssistantChatConsumer.as_asgi()),
]
