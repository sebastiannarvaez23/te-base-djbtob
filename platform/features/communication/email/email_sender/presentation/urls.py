from django.urls import path
from platform.features.communication.email.email_sender.presentation.api import (
    EmailSenderListCreateView, EmailSenderDetailView,
)

urlpatterns = [
    path('', EmailSenderListCreateView.as_view()),
    path('<uuid:pk>/', EmailSenderDetailView.as_view()),
]
