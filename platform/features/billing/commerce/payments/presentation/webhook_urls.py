from django.urls import path

from .webhooks import PaymentWebhookView


urlpatterns = [
    path('<str:provider>/', PaymentWebhookView.as_view(), name='payment-webhook'),
]
