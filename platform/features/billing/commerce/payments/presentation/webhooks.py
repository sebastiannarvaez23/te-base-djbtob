"""
Endpoint público de webhooks entrantes.

Convención: ``POST /api/v1/billing/webhooks/<provider>/``

Flujo:
  1. Recibimos payload crudo + headers.
  2. Verificamos la firma con el adapter del provider.
  3. Persistimos en la inbox (idempotente por ``provider+external_id``).
  4. Disparamos :class:`ProcessWebhookUseCase` de inmediato. Si falla,
     el inbox queda como ``processed_at IS NULL`` y un worker puede
     reintentar.
  5. Respondemos 200 SIEMPRE (excepto si la firma es inválida — 400),
     para evitar que el provider haga retries infinitos.

Notas:
  * El handler global de excepciones se omite aquí para no dar pistas
    a un atacante; capturamos todo y respondemos genéricamente.
  * No exige autenticación de usuario — la firma del provider es la
    autenticación.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.errors import AppErrorCode, AppException

from ..application.use_cases import ProcessWebhookUseCase
from ..domain.enums import GatewayProvider
from ..infrastructure.gateways.factory import get_payment_gateway
from ..infrastructure.repositories import (
    DjangoChargeRepository,
    DjangoWebhookInboxRepository,
)
from ..infrastructure.routing.router import DefaultPaymentRouter
from ..infrastructure.webhooks.inbox import store_raw_event


# Header en el que cada provider envía la firma. Mantener el mismo
# nombre para todos simplifica los adapters; el contenido es opaco.
SIGNATURE_HEADER = 'HTTP_X_PAYMENT_SIGNATURE'


class PaymentWebhookView(APIView):
    """Receptor de webhooks para cualquier proveedor registrado."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request, *args, **kwargs):
        provider_raw = kwargs.get('provider', '')
        try:
            provider = GatewayProvider(provider_raw)
        except ValueError:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_UNAVAILABLE,
                override_detail=f'Provider desconocido: {provider_raw!r}',
            )

        payload_bytes: bytes = request.body or b''
        signature_header = request.META.get(SIGNATURE_HEADER, '') or ''

        gateway = get_payment_gateway(provider)
        signature_verified = False
        try:
            signature_verified = gateway.verify_webhook_signature(payload_bytes, signature_header)
        except Exception:
            signature_verified = False

        if not signature_verified:
            raise AppException(AppErrorCode.PAY_WEBHOOK_INVALID)

        inbox_repo = DjangoWebhookInboxRepository()
        entry = store_raw_event(
            inbox_repo,
            provider=provider.value,
            payload_bytes=payload_bytes,
            signature_header=signature_header,
            signature_verified=True,
        )

        if entry is None:
            # Evento ya procesado anteriormente — respondemos OK.
            return wrap_response({'status': 'duplicate'}, message='Duplicate event ignored.')

        # Intento de procesamiento inmediato. Si falla, el worker reintentará.
        charge_repo = DjangoChargeRepository()
        try:
            ProcessWebhookUseCase(charge_repo, inbox_repo, DefaultPaymentRouter()).execute(entry)
        except AppException:
            # Errores conocidos (firma, transición rechazada) ya quedaron
            # registrados en la inbox; respondemos 200 igual.
            pass
        except Exception:
            # Errores inesperados: no rompemos contrato con el provider.
            pass

        return wrap_response({'status': 'accepted', 'inbox_id': str(entry.id)},
                             message='Webhook received.')
