from django.urls import path
from platform.features.communication.email.email_template.presentation.api import (
    EmailTemplateDetailView,
    EmailTemplateListCreateView,
    SendEmailView,
)

urlpatterns = [
    path('', EmailTemplateListCreateView.as_view()),
    path('<uuid:pk>/', EmailTemplateDetailView.as_view()),
    path('send/', SendEmailView.as_view()),
]
