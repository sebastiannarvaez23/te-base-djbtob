from django.urls import path
from platform.features.billing.subscription.subscription_limit.presentation.api import (
    SubscriptionLimitBySubscriptionView,
    SubscriptionLimitDetailView,
    SubscriptionLimitListCreateView,
)

urlpatterns = [
    path('', SubscriptionLimitListCreateView.as_view()),
    path('<uuid:pk>/', SubscriptionLimitDetailView.as_view()),
    path('by-subscription/<uuid:subscription_id>/', SubscriptionLimitBySubscriptionView.as_view()),
]
