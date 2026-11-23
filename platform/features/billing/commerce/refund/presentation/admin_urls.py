from django.urls import path

from .admin_api import (
    AdminRefundApproveView,
    AdminRefundDetailView,
    AdminRefundListView,
    AdminRefundRejectView,
)

urlpatterns = [
    path('', AdminRefundListView.as_view()),
    path('<uuid:ticket_id>/', AdminRefundDetailView.as_view()),
    path('<uuid:ticket_id>/approve/', AdminRefundApproveView.as_view()),
    path('<uuid:ticket_id>/reject/', AdminRefundRejectView.as_view()),
]
