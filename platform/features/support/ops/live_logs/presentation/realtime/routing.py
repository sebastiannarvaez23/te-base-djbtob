from django.urls import path

from platform.features.support.ops.live_logs.presentation.realtime.consumer import (
    LiveLogsConsumer,
)

websocket_urlpatterns = [
    path('ws/platform/live-logs/', LiveLogsConsumer.as_asgi()),
]
