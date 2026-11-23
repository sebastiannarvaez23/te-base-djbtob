"""
core/access/decorators.py
─────────────────────────
Decoradores para registrar consumo de features después de
una operación exitosa.

Uso
───
    class PaymentMethodViewSet(viewsets.ModelViewSet):
        @track_usage('settings.payment-methods.create')
        def create(self, request, *args, **kwargs):
            ...

        @untrack_usage('settings.payment-methods.create')
        def destroy(self, request, *args, **kwargs):
            ...

Los contadores solo se modifican si la vista retorna un status 2xx.
"""

from __future__ import annotations

import functools
import logging

from .checker import AccessChecker

logger = logging.getLogger('app.api')


def track_usage(feature_key: str):
    """Decorador que incrementa (+1) el contador de uso de una feature.

    Se aplica a métodos de vistas DRF (self, request, *args, **kwargs).
    Solo incrementa si la respuesta tiene status_code 2xx.

    Args:
        feature_key: clave de la funcionalidad a trackear.
    """

    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(self, request, *args, **kwargs):
            response = view_method(self, request, *args, **kwargs)

            if 200 <= response.status_code < 300:
                from core.permissions import company_for_request
                company = company_for_request(request)
                if company:
                    try:
                        AccessChecker.track_usage(company, feature_key)
                    except Exception:
                        logger.warning(
                            'Failed to track usage for feature=%s company=%s',
                            feature_key, company.id,
                            exc_info=True,
                        )

            return response
        return wrapper
    return decorator


def untrack_usage(feature_key: str):
    """Decorador que decrementa (-1) el contador de uso de una feature.

    Usado en operaciones de eliminación para mantener el contador
    sincronizado con la cantidad real de registros.

    Solo decrementa si la respuesta tiene status_code 2xx.

    Args:
        feature_key: clave de la funcionalidad a decrementar.
    """

    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(self, request, *args, **kwargs):
            response = view_method(self, request, *args, **kwargs)

            if 200 <= response.status_code < 300:
                from core.permissions import company_for_request
                company = company_for_request(request)
                if company:
                    try:
                        AccessChecker.untrack_usage(company, feature_key)
                    except Exception:
                        logger.warning(
                            'Failed to untrack usage for feature=%s company=%s',
                            feature_key, company.id,
                            exc_info=True,
                        )

            return response
        return wrapper
    return decorator
