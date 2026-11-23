from django.urls import path

from .api import ChargeViewSet


urlpatterns = [
    # CRUD principal
    path('', ChargeViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('company/<uuid:company_id>/', ChargeViewSet.as_view({'get': 'list_by_company'})),
    path('<uuid:pk>/', ChargeViewSet.as_view({'get': 'retrieve'})),

    # Transiciones de ciclo de vida
    path('<uuid:pk>/confirm/', ChargeViewSet.as_view({'post': 'confirm'})),
    path('<uuid:pk>/capture/', ChargeViewSet.as_view({'post': 'capture'})),
    path('<uuid:pk>/cancel/',  ChargeViewSet.as_view({'post': 'cancel'})),
    path('<uuid:pk>/refund/',  ChargeViewSet.as_view({'post': 'refund'})),
    path('<uuid:pk>/sync/',    ChargeViewSet.as_view({'post': 'sync'})),
]
