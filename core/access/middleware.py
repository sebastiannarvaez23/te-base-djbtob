"""
core/access/middleware.py
─────────────────────────
Middleware que pre-carga la suscripción activa de la empresa
en el request para evitar queries repetidos en los permission
classes y en la lógica de negocio.

Ubicación en el stack: después de TenantMainMiddleware.

El warm de features/catálogo y el enforcement MOD_004/SEC_003 viven en
``CatalogAccessMiddleware`` (``core.access.catalog_middleware``).
"""

from __future__ import annotations

import logging

from core.access.billing_recovery import is_billing_recovery_api_path

logger = logging.getLogger('app.api')


class SubscriptionMiddleware:
    """Pre-carga la suscripción activa y la adjunta a request.subscription.

    Si la empresa no tiene suscripción activa, request.subscription será None.
    El middleware es silencioso: nunca interrumpe el flujo del request.

    En el host SPA (``app.*`` / schema ``public``) ``request.tenant`` no es la
    empresa del usuario: se resuelve ``company_id`` desde el JWT cliente, igual
    que ``company_for_request``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.subscription = None
        request.subscription_id = None
        request.company_subscription_id = None

        company_id = self._resolve_company_id(request)
        if company_id:
            try:
                self._attach_subscription(request, company_id)
            except Exception:
                logger.warning(
                    'SubscriptionMiddleware: failed to load subscription for company=%s',
                    company_id,
                    exc_info=True,
                )

        return self.get_response(request)

    @classmethod
    def _resolve_company_id(cls, request) -> str | None:
        """Empresa del usuario cliente (JWT) o tenant del hostname."""
        company_id = cls._company_id_from_client_jwt(request)
        if company_id:
            return company_id

        tenant = getattr(request, 'tenant', None)
        if tenant is not None and getattr(tenant, 'id', None):
            return str(tenant.id)
        return None

    @staticmethod
    def _company_id_from_client_jwt(request) -> str | None:
        meta = getattr(request, 'META', None) or {}
        auth_ctx = str(meta.get('HTTP_X_AUTH_CONTEXT', '') or '').lower()
        if auth_ctx == 'admin':
            return None

        from core.auth.cookie_authentication import client_access_payload, get_client_user

        payload = client_access_payload(request)
        if not payload:
            return None
        user_id = payload.get('user_id')
        if not user_id:
            return None
        try:
            user = get_client_user(request, user_id)
        except Exception:
            logger.warning(
                'SubscriptionMiddleware: failed to resolve company from JWT user=%s',
                user_id,
                exc_info=True,
            )
            return None
        company_id = getattr(user, 'company_id', None) if user is not None else None
        return str(company_id) if company_id else None

    @staticmethod
    def _attach_subscription(request, company_id: str) -> None:
        from core.access.entitlement import entitled_acquisition_q
        from core.access.subscription import SubscriptionCache

        sub_id = SubscriptionCache.get_subscription_id(company_id)
        acq_id = SubscriptionCache.get_acquisition_id(company_id)
        if sub_id is None or (sub_id and acq_id is None):
            from platform.features.billing.subscription.subscription.models import CompanySubscription
            cs = (
                CompanySubscription.objects
                .filter(
                    entitled_acquisition_q(),
                    company_id=company_id,
                    subscription__is_active=True,
                )
                .select_related('subscription')
                .order_by('-start_date')
                .first()
            )

            if cs is not None:
                sub_id = str(cs.subscription_id)
                acq_id = str(cs.id)
                SubscriptionCache.set_subscription_id(company_id, sub_id)
                SubscriptionCache.set_acquisition_id(company_id, acq_id)
                request.subscription = cs
                request.subscription_id = sub_id
                request.company_subscription_id = acq_id
                from core.access.hooks import notify_subscription_expiry
                notify_subscription_expiry(company_id, cs)
            else:
                SubscriptionCache.set_subscription_id(company_id, '')
                SubscriptionCache.set_acquisition_id(company_id, '')
                request.subscription_id = None
                request.company_subscription_id = None
        elif sub_id:
            request.subscription_id = sub_id
            request.company_subscription_id = acq_id or None
        else:
            # Caché negativa ('') → sin plan activo.
            request.subscription_id = None
            request.company_subscription_id = None


class BillingRecoveryMiddleware:
    """Bloquea APIs operativas cuando el JWT está en ``billing_recovery``.

    Complementa ``HasSubscriptionAccess``: muchas vistas tenant solo exigen
    ``IsCompanyMember`` y quedarían abiertas sin este corte global.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.access_mode = self._resolve_access_mode(request)
        if request.access_mode == 'billing_recovery':
            if not is_billing_recovery_api_path(request.path):
                from django.http import JsonResponse
                from django.utils.timezone import now
                from core.errors.codes import ERROR_REGISTRY, AppErrorCode

                entry = ERROR_REGISTRY[AppErrorCode.SUB_RECOVERY_DENIED]
                trace_id = getattr(request, 'request_id', '')
                return JsonResponse(
                    {
                        'type': 'error',
                        'status_code': entry['http_status'],
                        'message': entry['message'],
                        'detail': entry['detail'],
                        'resolved_at': now().strftime('%Y-%m-%d %H:%M:%S'),
                        'error': {
                            'code': AppErrorCode.SUB_RECOVERY_DENIED.value,
                            'trace_id': trace_id,
                        },
                    },
                    status=entry['http_status'],
                )
        return self.get_response(request)

    @staticmethod
    def _resolve_access_mode(request) -> str:
        from core.auth.cookie_authentication import client_access_payload

        payload = client_access_payload(request)
        if not payload:
            return 'full'

        jwt_mode = payload.get('access_mode') or 'full'
        sub_id = getattr(request, 'subscription_id', None)
        if jwt_mode == 'full' and sub_id == '':
            return 'billing_recovery'
        if jwt_mode == 'full' and not sub_id:
            return jwt_mode
        return jwt_mode
