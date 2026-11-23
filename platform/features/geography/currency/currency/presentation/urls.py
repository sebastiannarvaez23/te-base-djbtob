from django.urls import path

from platform.features.geography.currency.currency.presentation.api import (
    AllowedCurrencyListView,
    CurrencyDetailView,
    CurrencyListCreateView,
)

urlpatterns = [
    path('allowed/', AllowedCurrencyListView.as_view(), name='geo-currencies-allowed'),
    path('', CurrencyListCreateView.as_view(), name='geo-currencies'),
    path('<uuid:pk>/', CurrencyDetailView.as_view(), name='geo-currency-detail'),
]
