"""
core/permissions.py
-------------------
Permisos personalizados reutilizables para DRF.
"""

import logging
import uuid

from rest_framework.permissions import BasePermission

from core.access.checker import AccessChecker
from core.access.billing_recovery import (
    get_request_access_mode,
    is_billing_recovery_feature,
    is_company_admin,
)
from core.errors.codes import AppErrorCode
from core.errors.exceptions import PermissionException, SubscriptionException

logger = logging.getLogger('app.api')


def _is_company_id(value) -> bool:
    if value is None:
        return False
    if isinstance(value, uuid.UUID):
        return True
    if isinstance(value, int):
        return True
    return isinstance(value, str) and bool(value)


def company_for_request(request):
    """JWT company first so tenant views work on the public URLconf (SPA host)."""
    user = getattr(request, 'user', None)
    company_id = getattr(user, 'company_id', None) if user is not None else None
    if _is_company_id(company_id):
        company = getattr(user, 'company', None)
        if company is not None:
            return company
    return getattr(request, 'tenant', None)


def _admin_has_complement(user, feature_key: str) -> bool:
    """El administrador de la empresa usa un complemento sin marcarlo en el rol.

    La licencia es de la empresa. El rol Administrator la recibe al otorgarla;
    el resto de roles solo la tiene si el administrador se la asignó.
    """
    company_id = getattr(user, 'company_id', None)
    if not company_id or not is_company_admin(user):
        return False
    from platform.features.billing.complement.entitlement.infrastructure.active import (
        active_complement_access,
    )
    keys, _modules = active_complement_access(str(company_id))
    return feature_key in keys


class IsCompanyMember(BasePermission):
    """Permite acceso solo si el usuario pertenece a una empresa (tenant)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'company_id')
            and request.user.company_id is not None
        )


class IsCompanyAdmin(BasePermission):
    """Solo el rol Administrator de la empresa (p. ej. otorgar accesos)."""

    def has_permission(self, request, view):
        if not IsCompanyMember().has_permission(request, view):
            return False
        if not is_company_admin(request.user):
            raise PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        return True


class HasSubscriptionAccess(BasePermission):
    """Verifica que la suscripción activa de la empresa permita la funcionalidad.

    La vista debe declarar el atributo ``subscription_functionality`` con la clave
    de la funcionalidad que se quiere proteger.

    Formatos soportados
    ───────────────────
    1. String (una clave para toda la vista):

        class CreateOrderView(APIView):
            permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
            subscription_functionality = 'orders.create'

    2. Dict (una clave por acción/método HTTP):

        class PaymentMethodViewSet(viewsets.ModelViewSet):
            permission_classes = [HasSubscriptionAccess]
            subscription_functionality = {
                'list':           'settings.payment-methods.view',
                'create':         'settings.payment-methods.create',
                'partial_update': 'settings.payment-methods.edit',
                'destroy':        'settings.payment-methods.delete',
            }

    3. Método ``get_subscription_functionality(request)`` en la vista
       para lógica dinámica (ej: distintas keys según los campos del body).

    Si la vista no declara ``subscription_functionality`` ni el método,
    el permiso pasa sin verificación (fail-open para vistas genéricas).

    ``subscription_check_quota`` (default True) controla si se evalúan
    topes (SUB_003). Lecturas (historial, status) deben ponerlo en False
    para que el cupo agotado solo bloquee el consumo, no consultar datos.

    Cuando el acceso es denegado, lanza SubscriptionException con el
    código apropiado (SUB_001, SUB_002, SUB_003) para que el error
    handler genere la respuesta estructurada y el frontend pueda
    diferenciar entre denegación por rol vs. por suscripción.
    """

    def has_permission(self, request, view):
        feature_key = self._resolve_feature_key(request, view)
        if not feature_key:
            return True

        company = company_for_request(request)
        if not company:
            return True  # Sin tenant → no aplica (admin portal, etc.)

        keys = feature_key if isinstance(feature_key, (list, tuple)) else [feature_key]

        if get_request_access_mode(request) == 'billing_recovery':
            for key in keys:
                if not is_billing_recovery_feature(key):
                    logger.info(
                        '[HasSubscriptionAccess] RECOVERY DENIED company=%s key=%s',
                        company.id, key,
                    )
                    raise SubscriptionException(
                        AppErrorCode.SUB_RECOVERY_DENIED,
                        context={'feature_key': key},
                    )
            return True

        check_quota = bool(getattr(view, 'subscription_check_quota', True))

        for key in keys:
            result = AccessChecker.check_feature(company, key, check_quota=check_quota)
            if not result.is_allowed:
                logger.info('[HasSubscriptionAccess] DENIED company=%s key=%s code=%s detail=%s',
                            company.id, key, result.error_code, result.detail)
                catalog_codes = {
                    AppErrorCode.MODULE_INACTIVE,
                    AppErrorCode.SECTION_INACTIVE,
                    AppErrorCode.FUNC_INACTIVE,
                }
                if result.error_code in catalog_codes:
                    from core.errors.exceptions import PermissionException
                    raise PermissionException(
                        result.error_code,
                        override_detail=result.detail,
                        context=result.context,
                    )
                raise SubscriptionException(
                    result.error_code,
                    override_detail=result.detail,
                    context=result.context,
                )
            self._assert_role_allows(request, key)

        return True

    @staticmethod
    def _assert_role_allows(request, feature_key: str) -> None:
        """Deniega si el rol del usuario no concede la feature (PERM_002)."""
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return
        rol = getattr(user, 'rol', None)
        role_id = getattr(user, 'rol_id', None) or getattr(rol, 'id', None)
        if not role_id:
            return
        if rol is not None and not getattr(rol, 'is_active', True):
            from core.errors.exceptions import AuthException
            raise AuthException(AppErrorCode.AUTH_ROLE_DISABLED)

        from core.access.role_cache import RoleFeatureCache
        from core.errors.exceptions import PermissionException

        role_keys = RoleFeatureCache.get_or_load(str(role_id))
        if feature_key not in role_keys and not _admin_has_complement(user, feature_key):
            logger.info(
                '[HasSubscriptionAccess] ROLE DENIED user=%s role=%s key=%s',
                getattr(user, 'pk', None), role_id, feature_key,
            )
            raise PermissionException(
                AppErrorCode.PERM_FEATURE_NOT_ALLOWED,
                context={'feature_key': feature_key},
            )

    @staticmethod
    def _resolve_feature_key(request, view):
        """Determina la feature key a validar según la configuración de la vista."""
        # 1. Método dinámico en la vista (máxima flexibilidad)
        resolver = getattr(view, 'get_subscription_functionality', None)
        if callable(resolver):
            return resolver(request)

        # 2. Atributo estático (string o dict)
        functionality = getattr(view, 'subscription_functionality', None)
        if not functionality:
            return None

        if isinstance(functionality, dict):
            # ViewSet → view.action ('list', 'create', …)
            # APIView → request.method en minúsculas ('get', 'post', …)
            action = getattr(view, 'action', None) or request.method.lower()
            return functionality.get(action)

        return functionality
