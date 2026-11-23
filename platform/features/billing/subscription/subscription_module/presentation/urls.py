from django.urls import path
from platform.features.billing.subscription.subscription_module.presentation.api import (
    SubscriptionModulesBySubscriptionView,
    SubscriptionModulesUpdateView,
)

urlpatterns = [
    path('by-subscription/<uuid:subscription_id>/', SubscriptionModulesBySubscriptionView.as_view()),
    path('<uuid:subscription_id>/', SubscriptionModulesUpdateView.as_view()),
]
