"""
core/access/subscription.py
────────────────────────────
Caché de la suscripción activa de una empresa.

Almacena en Redis (vía el backend de caché 'access') las features
habilitadas y los topes configurados del plan activo, evitando
consultas a PostgreSQL en cada request.

Convención de claves
────────────────────
    sub:{company_id}:features   → set[str]   (TTL 5 min)
    sub:{company_id}:limits     → dict       (TTL 5 min)
    sub:{company_id}:id         → str        (TTL 5 min)  plan catalog id
    sub:{company_id}:acquisition → str       (TTL 5 min)  CompanySubscription id
    sub:{company_id}:epoch      → int        (TTL 5 min)  snapshot del catálogo
    sub:{company_id}:complements → (keys, modules) (TTL 5 min) licencias de complemento
    access:catalog:epoch        → int        (sin TTL)    bump al mutar catálogo
"""

from __future__ import annotations

import logging
from typing import Optional

from django.core.cache import caches

logger = logging.getLogger('app.api')

_TTL = 300  # 5 minutos
_CATALOG_EPOCH_KEY = 'access:catalog:epoch'


def _cache():
    """Retorna el backend de caché 'access' (Redis)."""
    return caches['access']


class SubscriptionCache:
    """Caché de features y límites del plan activo de una empresa."""

    # ── Catalog epoch (invalidación transversal) ──────────────────────

    @staticmethod
    def get_catalog_epoch() -> int:
        try:
            return int(_cache().get(_CATALOG_EPOCH_KEY) or 0)
        except Exception:
            return 0

    @staticmethod
    def bump_catalog_epoch() -> int:
        """Incrementa el epoch global del catálogo (módulo/func/plan).

        Las lecturas de features/limits/id tratan epoch distinto como miss,
        forzando reload desde PostgreSQL en el siguiente request.
        """
        cache = _cache()
        try:
            return int(cache.incr(_CATALOG_EPOCH_KEY))
        except ValueError:
            cache.set(_CATALOG_EPOCH_KEY, 1)
            return 1
        except Exception:
            try:
                cache.set(_CATALOG_EPOCH_KEY, 1)
            except Exception:
                pass
            return 1

    @staticmethod
    def _company_epoch_key(company_id: str) -> str:
        return f'sub:{company_id}:epoch'

    @staticmethod
    def _is_fresh(company_id: str) -> bool:
        global_ep = SubscriptionCache.get_catalog_epoch()
        if global_ep == 0:
            # Catálogo sin bumps desde el arranque → snapshots legacy válidos.
            return True
        local = _cache().get(SubscriptionCache._company_epoch_key(company_id))
        if local is None:
            return False
        try:
            return int(local) == global_ep
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _stamp_company_epoch(company_id: str) -> None:
        _cache().set(
            SubscriptionCache._company_epoch_key(company_id),
            SubscriptionCache.get_catalog_epoch(),
            timeout=_TTL,
        )

    # ── Features habilitadas ──────────────────────────────────────────

    @staticmethod
    def get_features(company_id: str) -> Optional[set[str]]:
        """Retorna el set de feature keys habilitadas, o None si no está en caché."""
        if not SubscriptionCache._is_fresh(company_id):
            return None
        return _cache().get(f'sub:{company_id}:features')

    @staticmethod
    def set_features(company_id: str, features: set[str]) -> None:
        _cache().set(f'sub:{company_id}:features', features, timeout=_TTL)
        SubscriptionCache._stamp_company_epoch(company_id)

    # ── Topes configurados ────────────────────────────────────────────

    @staticmethod
    def get_limits(company_id: str) -> Optional[dict]:
        """Retorna dict {feature_key: {max: int, type: str, window_hours?: int}}, o None si no está en caché."""
        if not SubscriptionCache._is_fresh(company_id):
            return None
        return _cache().get(f'sub:{company_id}:limits')

    @staticmethod
    def set_limits(company_id: str, limits: dict) -> None:
        _cache().set(f'sub:{company_id}:limits', limits, timeout=_TTL)
        SubscriptionCache._stamp_company_epoch(company_id)

    # ── Subscription ID ───────────────────────────────────────────────

    @staticmethod
    def get_subscription_id(company_id: str) -> Optional[str]:
        if not SubscriptionCache._is_fresh(company_id):
            return None
        return _cache().get(f'sub:{company_id}:id')

    @staticmethod
    def set_subscription_id(company_id: str, subscription_id: str) -> None:
        _cache().set(f'sub:{company_id}:id', subscription_id, timeout=_TTL)
        SubscriptionCache._stamp_company_epoch(company_id)

    @staticmethod
    def get_acquisition_id(company_id: str) -> Optional[str]:
        if not SubscriptionCache._is_fresh(company_id):
            return None
        return _cache().get(f'sub:{company_id}:acquisition')

    @staticmethod
    def get_complements(company_id: str) -> Optional[tuple[set[str], set[str]]]:
        """Licencias de complemento cacheadas, o None si hay que leerlas de la base."""
        raw = _cache().get(f'sub:{company_id}:complements')
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return None
        return set(raw[0]), set(raw[1])

    @staticmethod
    def set_complements(company_id: str, keys: set[str], modules: set[str]) -> None:
        _cache().set(
            f'sub:{company_id}:complements',
            (sorted(keys), sorted(modules)),
            timeout=_TTL,
        )

    @staticmethod
    def set_acquisition_id(company_id: str, acquisition_id: str) -> None:
        _cache().set(f'sub:{company_id}:acquisition', acquisition_id, timeout=_TTL)
        SubscriptionCache._stamp_company_epoch(company_id)

    # ── Invalidación ──────────────────────────────────────────────────

    @staticmethod
    def invalidate(company_id: str) -> None:
        """Invalida toda la caché de suscripción de una empresa.

        Debe llamarse cuando el admin modifica features, límites o
        cambia el plan de la empresa.
        """
        _cache().delete_many([
            f'sub:{company_id}:features',
            f'sub:{company_id}:limits',
            f'sub:{company_id}:id',
            f'sub:{company_id}:acquisition',
            f'sub:{company_id}:epoch',
            f'sub:{company_id}:complements',
        ])

    @staticmethod
    def invalidate_subscription(subscription_id: str) -> None:
        """Invalida caché de TODAS las empresas con un plan dado.

        Se usa cuando el admin modifica features o límites de un plan
        desde base-admin-web.
        """
        try:
            from platform.features.billing.subscription.subscription.models import CompanySubscription
            company_ids = CompanySubscription.objects.filter(
                subscription_id=subscription_id, status='active',
            ).values_list('company_id', flat=True)
            for cid in company_ids:
                SubscriptionCache.invalidate(str(cid))
        except Exception:
            logger.warning(
                'Failed to invalidate subscription cache for subscription_id=%s',
                subscription_id,
                exc_info=True,
            )

    @staticmethod
    def invalidate_by_functionality(functionality_id) -> None:
        """Invalida planes que incluyen la funcionalidad (toggle de catálogo)."""
        try:
            from platform.features.billing.subscription.subscription.models import (
                SubscriptionFunctionality,
            )
            plan_ids = (
                SubscriptionFunctionality.objects
                .filter(functionality_id=functionality_id)
                .values_list('subscription_id', flat=True)
                .distinct()
            )
            for sid in plan_ids:
                SubscriptionCache.invalidate_subscription(str(sid))
            from platform.features.billing.complement.entitlement.models import CompanyComplement
            company_ids = (
                CompanyComplement.objects.filter(
                    functionality_id=functionality_id,
                    status=CompanyComplement.Status.ACTIVE,
                )
                .values_list('company_id', flat=True)
                .distinct()
            )
            for cid in company_ids:
                SubscriptionCache.invalidate(str(cid))
        except Exception:
            logger.warning(
                'Failed to invalidate by functionality_id=%s',
                functionality_id,
                exc_info=True,
            )
        SubscriptionCache.bump_catalog_epoch()

    @staticmethod
    def invalidate_by_module(module_id) -> None:
        """Invalida planes ligados al módulo o a sus funcionalidades."""
        try:
            from platform.features.billing.subscription.subscription.models import (
                SubscriptionFunctionality,
                SubscriptionModule,
            )
            from platform.features.security.access.functionalities.models import Functionality
            from platform.features.security.access.modules.models import Module

            module = Module.objects.filter(id=module_id).only('code').first()
            plan_ids: set = set()
            if module is not None:
                plan_ids.update(
                    SubscriptionModule.objects
                    .filter(module_code=module.code)
                    .values_list('subscription_id', flat=True)
                )
            func_ids = Functionality.objects.filter(module_id=module_id).values_list('id', flat=True)
            plan_ids.update(
                SubscriptionFunctionality.objects
                .filter(functionality_id__in=func_ids)
                .values_list('subscription_id', flat=True)
            )
            for sid in plan_ids:
                SubscriptionCache.invalidate_subscription(str(sid))
        except Exception:
            logger.warning(
                'Failed to invalidate by module_id=%s',
                module_id,
                exc_info=True,
            )
        SubscriptionCache.bump_catalog_epoch()
