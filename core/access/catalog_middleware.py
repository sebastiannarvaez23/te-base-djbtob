"""
CatalogAccessMiddleware — enforcement de acceso transversal vía Redis.

Responsabilidades (aisladas de SubscriptionMiddleware):
  1. Precalentar features/limits de suscripción en Redis (miss → PG una vez).
  2. Precalentar snapshot de módulos/secciones activos.
  3. Sin plan activo (``request.subscription_id`` vacío tras el warm):
     denegar con SUB_001 en cualquier API cliente autenticada.
  4. Si la ruta API o el header X-UI-Context (``mc`` / ``mid``) apuntan
     a un módulo inactivo, denegar con MOD_004 / SEC_003. La ruta no
     se sustituye por el header: ambos se evalúan.

No sustituye ``HasSubscriptionAccess`` (features/cupos/rol); lo complementa
para APIs sin ``subscription_functionality``.
"""

from __future__ import annotations

import logging
import re

from django.http import JsonResponse
from django.utils.timezone import now

from core.access.billing_recovery import is_billing_recovery_api_path
from core.errors.codes import ERROR_REGISTRY, AppErrorCode

logger = logging.getLogger('app.api')

# Prefijos bajo /api/v1/ que nunca pasan por el gate de catálogo (módulo).
_SKIP_PREFIXES: tuple[str, ...] = (
    'auth/',
    'onboarding/',
    'subscriptions/',
    'landing/',
    'locations/',
    'policies/',
    'incidents/',
    'testimonials/',
    'platform/',
    'billing/webhooks/',
)

# Prefijos que NO aplican el gate SUB_001 (login / logout / públicos).
# ``auth/me`` y el resto de APIs autenticadas SÍ quedan bajo el gate.
_SUB_SKIP_PREFIXES: tuple[str, ...] = (
    'auth/login',
    'auth/logout',
    'auth/refresh',
    'auth/confirm-email',
    'auth/resend-confirmation',
    'auth/password-reset/',
    'onboarding/',
    'subscriptions/',
    'landing/',
    'locations/',
    'incidents/',
    'testimonials/',
    'platform/',
    'billing/webhooks/',
)

_MODULE_CODE_RE = re.compile(r'^[A-Za-z0-9_.\-]{1,100}$')

# APIs de un módulo operativo. Si la ruta no resuelve un módulo del
# catálogo, se deniega: el header no puede autorizarlas por sí solo.
_MODULE_BOUND_PREFIXES: tuple[str, ...] = (
    'company-users',
    'company-roles',
    'company-features',
    'integrations',
    'oauth',
    'assistant',
    'identity',
)


class CatalogAccessMiddleware:
    """Gate de suscripción + catálogo + warm de caché de acceso (Redis)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._warm_caches(request)

        denied = self._maybe_deny(request)
        if denied is not None:
            return denied

        return self.get_response(request)

    # ── Warm ──────────────────────────────────────────────────────────

    @staticmethod
    def _warm_caches(request) -> None:
        tenant = getattr(request, 'tenant', None)
        company_id = str(getattr(tenant, 'id', '') or '') or None
        sub_id = getattr(request, 'subscription_id', None)

        if company_id and sub_id:
            try:
                from core.access.checker import AccessChecker
                from core.access.subscription import SubscriptionCache

                if SubscriptionCache.get_features(company_id) is None:
                    AccessChecker._load_features(sub_id, company_id)
                if SubscriptionCache.get_limits(company_id) is None:
                    AccessChecker._load_limits(sub_id, company_id)
            except Exception:
                logger.warning(
                    'CatalogAccessMiddleware: warm features failed company=%s',
                    company_id,
                    exc_info=True,
                )

        try:
            from core.access.catalog_cache import CatalogStatusCache
            CatalogStatusCache.get_or_load()
        except Exception:
            logger.warning('CatalogAccessMiddleware: warm catalog snapshot failed', exc_info=True)

    # ── Enforce ───────────────────────────────────────────────────────

    def _maybe_deny(self, request) -> JsonResponse | None:
        if not self._is_client_api(request):
            return None

        # Modo recovery: BillingRecoveryMiddleware ya acota las rutas.
        if getattr(request, 'access_mode', None) == 'billing_recovery':
            return None

        # Gate global de suscripción: aplica aunque el path esté en skip
        # de catálogo (p. ej. auth/me) para cortar la sesión en caliente.
        if not self._is_subscription_skipped_path(request.path):
            if not getattr(request, 'subscription_id', None):
                entry = ERROR_REGISTRY[AppErrorCode.SUB_NO_ACTIVE]
                return self._error_response(
                    request,
                    AppErrorCode.SUB_NO_ACTIVE,
                    entry['detail'],
                    None,
                )

        if self._is_skipped_path(request.path):
            return None
        if is_billing_recovery_api_path(request.path):
            return None

        from core.access.catalog_cache import CatalogStatusCache

        path_code = CatalogStatusCache.resolve_code_from_api_path(request.path or '')
        if self._requires_resolved_module(request.path) and not path_code:
            entry = ERROR_REGISTRY[AppErrorCode.MODULE_INACTIVE]
            return self._error_response(
                request,
                AppErrorCode.MODULE_INACTIVE,
                entry['detail'],
                None,
            )

        # La ruta API es la fuente de verdad. El header se evalúa además:
        # un ``mc`` activo no oculta la API de un módulo inactivo.
        for module_code in self._module_codes(request, path_code=path_code):
            result = CatalogStatusCache.check_module_code(module_code)
            if result.is_allowed:
                continue
            code = result.error_code or AppErrorCode.MODULE_INACTIVE
            return self._error_response(request, code, result.detail, result.context)
        return None

    @staticmethod
    def _is_client_api(request) -> bool:
        path = request.path or ''
        if '/api/' not in path:
            return False
        # Misma regla que JWTAccessAuthentication: con X-Auth-Context: admin
        # no aplicar gates de sesión cliente (mismo browser puede tener ambas cookies).
        from core.auth.cookie_authentication import _auth_context
        if _auth_context(request) == 'admin':
            return False

        from core.auth.cookie_authentication import client_access_payload
        return client_access_payload(request) is not None

    @staticmethod
    def _api_v1_rest(path: str) -> str | None:
        raw = path or ''
        marker = '/api/v1/'
        if marker not in raw:
            return None
        return raw.split(marker, 1)[1]

    @classmethod
    def _is_skipped_path(cls, path: str) -> bool:
        rest = cls._api_v1_rest(path)
        if rest is None:
            return True
        return any(rest.startswith(p) for p in _SKIP_PREFIXES)

    @classmethod
    def _is_subscription_skipped_path(cls, path: str) -> bool:
        rest = cls._api_v1_rest(path)
        if rest is None:
            return True
        return any(rest.startswith(p) for p in _SUB_SKIP_PREFIXES)

    @classmethod
    def _requires_resolved_module(cls, path: str) -> bool:
        rest = cls._api_v1_rest(path) or ''
        rest = rest.strip('/')
        if not rest:
            return False
        return any(
            rest == prefix.rstrip('/') or rest.startswith(prefix.rstrip('/') + '/')
            for prefix in _MODULE_BOUND_PREFIXES
        )

    @classmethod
    def _module_codes(cls, request, path_code: str = '') -> list[str]:
        """Códigos a evaluar: ruta API y, si difiere, el módulo del header."""
        header_code = cls._header_module_code(request)
        codes: list[str] = []
        seen: set[str] = set()
        for code in (path_code, header_code):
            normalized = (code or '').strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            codes.append(normalized)
        return codes

    @staticmethod
    def _header_module_code(request) -> str:
        meta = getattr(request, 'META', {}) or {}
        raw = meta.get('HTTP_X_UI_CONTEXT') or ''
        if isinstance(raw, (list, tuple)):
            raw = raw[0] if raw else ''
        mc = ''
        mid = ''
        for part in str(raw).split(';'):
            token = part.strip()
            if token.startswith('mc=') and len(token) > 3:
                candidate = token[3:].strip()
                if _MODULE_CODE_RE.match(candidate):
                    mc = candidate
            elif token.startswith('mid=') and len(token) > 4:
                mid = token[4:].strip().lower()

        if mc:
            return mc

        if mid:
            from core.access.catalog_cache import CatalogStatusCache
            snap = CatalogStatusCache.get_or_load()
            if isinstance(snap, dict):
                return (snap.get('by_id') or {}).get(mid) or ''
        return ''

    @staticmethod
    def _error_response(request, code, detail: str, context: dict | None) -> JsonResponse:
        try:
            entry = ERROR_REGISTRY[code]
        except Exception:
            code = AppErrorCode.MODULE_INACTIVE
            entry = ERROR_REGISTRY[code]

        code_value = getattr(code, 'value', None) or str(code)
        payload = {
            'type': 'error',
            'status_code': entry['http_status'],
            'message': entry['message'],
            'detail': detail or entry['detail'],
            'resolved_at': now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': {
                'code': code_value,
                'detail': detail or entry['detail'],
                'trace_id': getattr(request, 'request_id', '') or '',
            },
        }
        if context:
            payload['error']['context'] = context
        return JsonResponse(
            payload,
            status=entry['http_status'],
            content_type='application/json',
        )
