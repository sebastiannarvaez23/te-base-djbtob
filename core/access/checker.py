"""
core/access/checker.py
──────────────────────
Orquestador principal del control de acceso por suscripción.

Flujo de verificación
─────────────────────
  1. ¿La empresa tiene suscripción activa?       → SUB_001
  2. ¿La feature está habilitada en el plan?      → SUB_002
  3. ¿Existe un tope configurado para la feature?
     → No: acceso libre (sin tope = ilimitado)
     → Sí: delegar al validador correspondiente   → SUB_003

Todas las lecturas se hacen contra Redis (O(1)), con fallback
automático a PostgreSQL cuando la caché expira (cada 5 min).
"""

from __future__ import annotations

import logging

from .result import AccessResult
from .subscription import SubscriptionCache
from .validators import DailyValidator, LifetimeValidator, LimitValidator, WindowValidator
from .enforcement import enforcement_registry

logger = logging.getLogger('app.api')


class AccessChecker:
    """Punto de entrada único para validar acceso por suscripción."""

    _validators: list[LimitValidator] = [
        DailyValidator(),
        LifetimeValidator(),
        WindowValidator(),
    ]

    # ── Verificación principal ────────────────────────────────────────

    @staticmethod
    def check_feature(company, feature_key: str, *, check_quota: bool = True) -> AccessResult:
        """Verifica feature habilitada + tope no excedido.

        Args:
            company: instancia del modelo Company (request.tenant).
            feature_key: clave de la funcionalidad (ej: 'orders.create').
            check_quota: si es False, no evalúa topes (lecturas: historial, status).

        Returns:
            AccessResult indicando si el acceso es permitido o denegado.
        """
        company_id = str(company.id)

        # 1. ¿Tiene suscripción activa?
        #    La caché distingue tres estados:
        #      None → no cacheado         → cargar de la BD.
        #      ''   → caché negativa       → se sabe que NO hay plan.
        #      uuid → suscripción activa.
        #    Se usa ``not subscription_id`` (y no ``is None``) para que la
        #    caché negativa ('') también corte con SUB_NO_ACTIVE en vez de
        #    continuar con un subscription_id vacío hacia SUB_FEATURE_DENIED.
        subscription_id = SubscriptionCache.get_subscription_id(company_id)
        if subscription_id is None:
            subscription_id = AccessChecker._load_subscription_id(company_id)
        if not subscription_id:
            return AccessResult.no_subscription()

        # 2. ¿La feature está habilitada en el plan?
        features = SubscriptionCache.get_features(company_id)
        if features is None:
            features = AccessChecker._load_features(subscription_id, company_id)

        if feature_key not in features:
            from core.access.catalog_status import diagnose_feature_key
            catalog = diagnose_feature_key(feature_key)
            if catalog is not None:
                return catalog
            return AccessResult.feature_denied(feature_key)

        if not check_quota:
            return AccessResult.allowed()

        # 3. ¿Hay tope configurado?
        limits = SubscriptionCache.get_limits(company_id)
        if limits is None:
            limits = AccessChecker._load_limits(subscription_id, company_id)

        limit_config = limits.get(feature_key)
        if not limit_config:
            return AccessResult.allowed()  # sin tope → acceso libre

        # 4. Delegar al validador correspondiente
        max_value = limit_config['max']
        validation_type = limit_config['type']
        extra = AccessChecker._validator_kwargs(limit_config)

        for validator in AccessChecker._validators:
            if validator.matches(validation_type):
                if (
                    validation_type == 'window'
                    and WindowValidator.resolve_hours(extra) is None
                ):
                    logger.error(
                        'window limit missing window_hours feature=%s company=%s — denying',
                        feature_key, company_id,
                    )
                    return AccessResult.quota_exceeded(
                        feature_key, max_value, max_value, validation_type,
                    )
                current = validator.get_current_usage(company_id, feature_key, **extra)
                if current >= max_value:
                    return AccessResult.quota_exceeded(
                        feature_key, max_value, current, validation_type,
                        resets_at=validator.quota_resets_at(**extra),
                    )
                return AccessResult.allowed()

        # Tipo de validación desconocido → permitir (fail-open) y loguear
        logger.warning(
            'Unknown validation_type=%s for feature=%s company=%s',
            validation_type, feature_key, company_id,
        )
        return AccessResult.allowed()

    @staticmethod
    def enabled_features(company) -> set[str]:
        """Feature keys enabled by the company's active plan (empty without plan)."""
        company_id = str(company.id)
        subscription_id = SubscriptionCache.get_subscription_id(company_id)
        if subscription_id is None:
            subscription_id = AccessChecker._load_subscription_id(company_id)
        if not subscription_id:
            return set()

        features = SubscriptionCache.get_features(company_id)
        if features is None:
            features = AccessChecker._load_features(subscription_id, company_id)
        return set(features)

    @staticmethod
    def ensure_quota_or_raise(company, feature_key: str) -> None:
        """
        Lanza SubscriptionException si el cupo está agotado (SUB_003 u otro).

        Usar en use cases al **crear** (recurso activo) y al **activar**.
        Guía: platform/features/billing/quota_enforcement/EXTENDING.md
        """
        AccessChecker.ensure_access_or_raise(company, feature_key, check_quota=True)

    @staticmethod
    def ensure_access_or_raise(company, feature_key: str, *, check_quota: bool = True) -> None:
        """Raise the catalog (PermissionException) or plan (SubscriptionException) denial."""
        from core.errors import AppErrorCode, SubscriptionException
        from core.errors.exceptions import PermissionException

        result = AccessChecker.check_feature(company, feature_key, check_quota=check_quota)
        if not result.is_allowed:
            catalog_codes = {
                AppErrorCode.MODULE_INACTIVE,
                AppErrorCode.SECTION_INACTIVE,
                AppErrorCode.FUNC_INACTIVE,
            }
            if result.error_code in catalog_codes:
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

    # ── Tracking de uso ───────────────────────────────────────────────

    @staticmethod
    def track_usage(company, feature_key: str) -> None:
        """Registra el consumo de una feature (llamar DESPUÉS de operación exitosa).

        Args:
            company: instancia del modelo Company.
            feature_key: clave de la funcionalidad consumida.
        """
        company_id = str(company.id)

        limits = SubscriptionCache.get_limits(company_id)
        if limits is None:
            subscription_id = SubscriptionCache.get_subscription_id(company_id)
            if not subscription_id:
                subscription_id = AccessChecker._load_subscription_id(company_id)
            if not subscription_id:
                return
            limits = AccessChecker._load_limits(subscription_id, company_id)

        limit_config = limits.get(feature_key)
        if not limit_config:
            return  # sin tope → nada que trackear

        if enforcement_registry.has(feature_key):
            return  # cupo activo: el conteo viene de BD en el próximo check

        validation_type = limit_config['type']
        max_value = limit_config.get('max')
        extra = AccessChecker._validator_kwargs(limit_config)
        for validator in AccessChecker._validators:
            if validator.matches(validation_type):
                new_value = validator.track(company_id, feature_key, **extra)
                # Detección de sobrepaso: el pre-check (check_feature) y este
                # track ocurren en operaciones separadas, así que dos requests
                # concurrentes con current == max-1 pueden ambos pasar el
                # chequeo y ambos incrementar. El INCR de Redis es atómico, de
                # modo que el contador nunca se corrompe, pero PUEDE quedar
                # por encima del tope bajo alta concurrencia. Aquí no revertimos
                # (el contador refleja recursos reales creados), solo dejamos el
                # sobrepaso visible en logs. Para un tope DURO 100% infalible la
                # verificación debe ser atómica con la escritura en PostgreSQL
                # (constraint / SELECT … FOR UPDATE en la misma transacción):
                # Redis por sí solo es un gate optimista, no transaccional.
                if (
                    isinstance(new_value, int)
                    and isinstance(max_value, int)
                    and new_value > max_value
                ):
                    logger.warning(
                        'QUOTA_BREACH company=%s feature=%s type=%s usage=%s max=%s '
                        '(carrera en el gate; contador por encima del tope)',
                        company_id, feature_key, validation_type, new_value, max_value,
                    )
                return

    @staticmethod
    def untrack_usage(company, feature_key: str) -> None:
        """Decrementa el consumo de una feature (llamar DESPUÉS de eliminación exitosa).

        Args:
            company: instancia del modelo Company.
            feature_key: clave de la funcionalidad a decrementar.
        """
        company_id = str(company.id)

        limits = SubscriptionCache.get_limits(company_id)
        if limits is None:
            subscription_id = SubscriptionCache.get_subscription_id(company_id)
            if not subscription_id:
                subscription_id = AccessChecker._load_subscription_id(company_id)
            if not subscription_id:
                return
            limits = AccessChecker._load_limits(subscription_id, company_id)

        limit_config = limits.get(feature_key)
        if not limit_config:
            return

        if enforcement_registry.has(feature_key):
            return

        validation_type = limit_config['type']
        extra = AccessChecker._validator_kwargs(limit_config)
        for validator in AccessChecker._validators:
            if validator.matches(validation_type):
                validator.untrack(company_id, feature_key, **extra)
                return

    # ── Loaders (fallback a DB, resultado se cachea) ──────────────────

    @staticmethod
    def _validator_kwargs(limit_config: dict) -> dict:
        """Argumentos extra que algunos validadores necesitan (ej. window_hours)."""
        hours = limit_config.get('window_hours')
        return {'window_hours': hours} if hours is not None else {}

    @staticmethod
    def _load_subscription_id(company_id: str) -> str | None:
        """Carga el ID de la suscripción activa desde PostgreSQL."""
        try:
            from core.access.entitlement import entitled_acquisition_q
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

            if cs is None:
                SubscriptionCache.set_subscription_id(company_id, '')
                SubscriptionCache.set_acquisition_id(company_id, '')
                return None

            sub_id = str(cs.subscription_id)
            SubscriptionCache.set_subscription_id(company_id, sub_id)
            SubscriptionCache.set_acquisition_id(company_id, str(cs.id))
            return sub_id
        except Exception:
            logger.warning('Failed to load subscription for company=%s', company_id, exc_info=True)
            return None

    @staticmethod
    def _load_features(subscription_id: str, company_id: str) -> set[str]:
        """Carga las features habilitadas del plan desde PostgreSQL.

        Solo incluye funcionalidades activas cuyo módulo también esté activo.
        """
        try:
            from platform.features.billing.subscription.subscription.models import (
                Subscription,
                SubscriptionFunctionality,
            )
            plan_active = Subscription.objects.filter(
                id=subscription_id, is_active=True,
            ).exists()
            if not plan_active:
                SubscriptionCache.set_features(company_id, set())
                return set()

            keys = set(
                SubscriptionFunctionality.objects.filter(
                    subscription_id=subscription_id,
                    functionality__is_active=True,
                    functionality__module__is_active=True,
                    functionality__module__section__is_active=True,
                ).values_list('functionality__key', flat=True)
            )
            from platform.features.billing.complement.entitlement.infrastructure.active import (
                active_complement_access,
            )
            keys |= active_complement_access(company_id)[0]
            SubscriptionCache.set_features(company_id, keys)
            return keys
        except Exception:
            logger.warning('Failed to load features for subscription=%s', subscription_id, exc_info=True)
            return set()

    @staticmethod
    def _load_limits(subscription_id: str, company_id: str) -> dict:
        """Carga los topes configurados del plan desde PostgreSQL.

        Returns:
            dict con formato {feature_key: {'max': int, 'type': str, 'window_hours': int|None}}
        """
        try:
            from platform.features.billing.subscription.subscription_limit.models import SubscriptionLimit
            qs = SubscriptionLimit.objects.filter(
                subscription_id=subscription_id,
            ).select_related('functionality')

            limits = {
                sl.functionality.key: {
                    'max': sl.max_value,
                    'type': sl.validation_type,
                    'window_hours': sl.window_hours,
                }
                for sl in qs
            }
            SubscriptionCache.set_limits(company_id, limits)
            return limits
        except Exception:
            logger.warning('Failed to load limits for subscription=%s', subscription_id, exc_info=True)
            return {}
