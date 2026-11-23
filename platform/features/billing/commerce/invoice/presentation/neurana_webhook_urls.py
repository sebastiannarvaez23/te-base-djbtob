from django.urls import path

from platform.features.billing.commerce.invoice.presentation.neurana_webhooks import (
    neurana_webhook,
)

urlpatterns = [
    path('neurana/', neurana_webhook, name='ecosystem-webhook-neurana'),
]
