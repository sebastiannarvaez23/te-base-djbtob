from django.urls import path

from .api import (
    CurrentRefundView,
    RefundEligibilityView,
    RefundPreviewView,
    RefundRequestView,
)

urlpatterns = [
    path('eligibility/', RefundEligibilityView.as_view()),
    path('preview/', RefundPreviewView.as_view()),
    path('current/', CurrentRefundView.as_view()),
    path('tickets/', RefundRequestView.as_view()),
    path('', RefundRequestView.as_view()),
]
