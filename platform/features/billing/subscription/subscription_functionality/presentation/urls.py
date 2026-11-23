from django.urls import path
from platform.features.billing.subscription.subscription_functionality.presentation.api import (
    SubscriptionFunctionalitiesBySubscriptionView,
    SubscriptionFunctionalitiesUpdateView,
)

urlpatterns = [
    path('by-subscription/<uuid:subscription_id>/', SubscriptionFunctionalitiesBySubscriptionView.as_view()),
    path('<uuid:subscription_id>/', SubscriptionFunctionalitiesUpdateView.as_view()),
]
