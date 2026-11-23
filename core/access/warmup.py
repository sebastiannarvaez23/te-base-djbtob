"""
core/access/warmup.py
─────────────────────
Pre-carga en Redis toda la información necesaria para que las
validaciones de topes funcionen sin consultar PostgreSQL.

Se ejecuta una sola vez al levantar el servidor (llamado desde
SubscriptionAppConfig.ready()).

Flujo
─────
  1. Verifica conectividad con Redis.
  2. Para cada empresa con suscripción activa, carga en Redis:
     - subscription_id
     - features habilitadas (set de keys)
     - topes configurados (dict {feature_key: {max, type, window_hours}})
  3. Para cada tope lifetime con counter registrado, siembra el
     conteo real desde la BD en el contador de Redis.

Después del warmup, toda la validación de topes es 100% Redis (O(1)).
"""

from __future__ import annotations

import logging
import sys

from django.core.cache import caches

from .registry import usage_registry
from .store import UsageStore
from .subscription import SubscriptionCache

logger = logging.getLogger('app.api')

_OK  = 'OK'
_ERR = 'ERROR'

_BANNER = r"""
 __      __  _           ___   ___   ___  ___         __  __   ___   _  _
 \ \    / / /_\   ___   / __| / _ \ | _ \| __|  ___  |  \/  | / _ \ | \| |
  \ \/\/ / / _ \ |___| | (__ | (_) ||   /| _|  |___| | |\/| || (_) || .` |
   \_/\_/ /_/ \_\       \___| \___/ |_|_\|___|       |_|  |_| \___/ |_|\_|

                                                              (v1.0)
"""

_RUNSERVER_BLANK_PATCHED = False


def ensure_blank_line_after_runserver_banner() -> None:
    """Blank line after Daphne's ``Quit the server with …`` before request logs."""
    global _RUNSERVER_BLANK_PATCHED
    if _RUNSERVER_BLANK_PATCHED:
        return
    try:
        from daphne.management.commands.runserver import Command
    except ImportError:
        return

    original = Command.inner_run

    def inner_run(self, *args, **options):
        wrapped = self.stdout

        class _Out:
            def write(self_inner, msg=''):
                wrapped.write(msg)
                if isinstance(msg, str) and 'Quit the server with' in msg:
                    wrapped.write('\n')

            def flush(self_inner):
                return wrapped.flush()

            def __getattr__(self_inner, name):
                return getattr(wrapped, name)

        self.stdout = _Out()
        try:
            return original(self, *args, **options)
        finally:
            self.stdout = wrapped

    Command.inner_run = inner_run
    _RUNSERVER_BLANK_PATCHED = True


def _print_banner() -> None:
    """Imprime el banner estilo SpringBoot al levantar el servidor."""
    sys.stdout.write(_BANNER + '\n')
    sys.stdout.flush()


def _register_counters() -> None:
    """Registra los counters de BD para todas las features conocidas.

    Se ejecuta dentro del warmup para no depender del Pedidos de
    carga de AppConfig.ready() entre módulos.
    """
    from platform.features.billing.commerce.payment_method.models import PaymentMethod

    usage_registry.register(
        'settings.payment-methods.create',
        lambda company_id: PaymentMethod.objects.filter(company_id=company_id).count(),
    )


def warmup_subscription_cache() -> None:
    """Verifica conexiones de servicios y pre-carga la caché de suscripción en Redis."""

    _print_banner()

    _register_counters()

    pg_status         = _check_postgres()
    redis_status      = _check_redis()
    minio_status      = _check_minio()
    ai_runtime_status = _check_ai_runtime()
    workers_status    = _check_workers()
    beat_status       = _check_beat()
    erp_status        = _check_erp()

    logger.info('[startup]   PostgreSQL : %s', pg_status)
    logger.info('[startup]   Redis      : %s', redis_status)
    logger.info('[startup]   MinIO      : %s', minio_status)
    logger.info('[startup]   AI-runtime : %s', ai_runtime_status)
    logger.info('[startup]   Workers    : %s', workers_status)
    logger.info('[startup]   Beat       : %s', beat_status)
    logger.info('[startup]   ERP        : %s', erp_status)

    if redis_status != _OK:
        logger.warning(
            '[access:warmup] Redis no disponible — '
            'las validaciones de topes NO funcionarán correctamente.'
        )
        return

    # ── Cargar datos de todas las empresas activas ─────────────────────
    try:
        from platform.features.billing.subscription.subscription.models import (
            CompanySubscription,
            SubscriptionFunctionality,
        )
        from platform.features.billing.subscription.subscription_limit.models import SubscriptionLimit

        from core.access.entitlement import entitled_acquisition_q

        active_subs = list(
            CompanySubscription.objects
            .filter(entitled_acquisition_q(), subscription__is_active=True)
            .values_list('company_id', 'subscription_id', 'id')
        )

        if not active_subs:
            return

        from platform.features.billing.complement.entitlement.infrastructure.active import (
            active_complement_keys_by_company,
        )
        complement_keys_by_company = active_complement_keys_by_company()

        sub_features: dict[str, set[str]] = {}
        sub_limits: dict[str, dict] = {}

        company_count = 0
        counter_count = 0

        for company_id, subscription_id, acquisition_id in active_subs:
            company_id_str = str(company_id)
            sub_id_str = str(subscription_id)

            SubscriptionCache.set_subscription_id(company_id_str, sub_id_str)
            SubscriptionCache.set_acquisition_id(company_id_str, str(acquisition_id))

            if sub_id_str not in sub_features:
                sub_features[sub_id_str] = set(
                    SubscriptionFunctionality.objects
                    .filter(subscription_id=subscription_id, functionality__is_active=True)
                    .values_list('functionality__key', flat=True)
                )
            features = set(sub_features[sub_id_str])
            features |= complement_keys_by_company.get(company_id_str, set())
            SubscriptionCache.set_features(company_id_str, features)

            if sub_id_str not in sub_limits:
                qs = SubscriptionLimit.objects.filter(
                    subscription_id=subscription_id,
                ).select_related('functionality')
                sub_limits[sub_id_str] = {
                    sl.functionality.key: {
                        'max': sl.max_value,
                        'type': sl.validation_type,
                        'window_hours': sl.window_hours,
                    }
                    for sl in qs
                }
            SubscriptionCache.set_limits(company_id_str, sub_limits[sub_id_str])

            limits = sub_limits[sub_id_str]
            for feature_key, config in limits.items():
                if config['type'] != 'lifetime':
                    continue
                if not usage_registry.has_counter(feature_key):
                    continue
                real_count = usage_registry.get_count(feature_key, company_id_str)
                if real_count is not None:
                    UsageStore.set_lifetime(company_id_str, feature_key, real_count)
                    counter_count += 1

            company_count += 1

    except Exception:
        logger.warning(
            '[access:warmup] Error al cargar caché de suscripción.',
            exc_info=True,
        )


def _check_postgres() -> str:
    """Verifica conectividad con PostgreSQL."""
    try:
        from django.db import connection
        connection.ensure_connection()
        return _OK
    except Exception:
        return _ERR


def _check_redis() -> str:
    """Verifica conectividad con Redis."""
    try:
        cache = caches['access']
        cache.set('_warmup_ping', '1', timeout=10)
        val = cache.get('_warmup_ping')
        if val == '1':
            cache.delete('_warmup_ping')
            return _OK
        return _ERR
    except Exception:
        return _ERR


def _check_minio() -> str:
    """Verifica conectividad con MinIO."""
    try:
        from django.conf import settings
        from minio import Minio
        client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        client.list_buckets()
        return _OK
    except Exception:
        return _ERR


def _check_ai_runtime() -> str:
    """Verifica el runtime de inferencia según ``AI_PROVIDER``."""
    try:
        from django.conf import settings

        from core.ai.health import probe_inference_health

        provider = getattr(settings, 'AI_PROVIDER', 'fake') or 'fake'
        return _OK if probe_inference_health(provider) == 'ok' else _ERR
    except Exception:
        return _ERR


def _check_workers() -> str:
    """Verifica que al menos un worker Celery responda al ping del broker."""
    try:
        from core.tasks.app import app

        inspect = app.control.inspect(timeout=1.0)
        if inspect is None:
            return _ERR
        pong = inspect.ping()
        return _OK if pong else _ERR
    except Exception:
        return _ERR


def _check_beat() -> str:
    """Verifica que RedBeat tenga el candado activo en Redis."""
    try:
        import redis
        from django.conf import settings

        client = redis.from_url(settings.CELERY_REDBEAT_REDIS_URL)
        return _OK if client.exists('redbeat::lock') else _ERR
    except Exception:
        return _ERR


def _check_erp() -> str:
    """Verifica ne-core-mon (ERP).

    Con credenciales de producto llama al health autenticado del ecosistema
    (token + JWKS + firma); sin ellas solo comprueba TCP en
    ``NE_ECOSYSTEM_BASE_URL``.
    """
    try:
        from django.conf import settings

        if (getattr(settings, 'NE_PRODUCT_CLIENT_ID', '') or '').strip():
            from platform.features.billing.commerce.invoice.infrastructure.fiscal.ecosystem_client import (
                get_ecosystem_client,
            )

            get_ecosystem_client().health()
            return _OK
    except Exception:
        return _ERR
    return _check_erp_tcp()


def _check_erp_tcp() -> str:
    try:
        import socket
        from urllib.parse import urlparse

        from django.conf import settings

        base = (getattr(settings, 'NE_ECOSYSTEM_BASE_URL', '') or '').strip()
        if not base:
            return _ERR
        parsed = urlparse(base if '://' in base else f'http://{base}')
        host = parsed.hostname
        if not host:
            return _ERR
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        with socket.create_connection((host, port), timeout=2.0):
            return _OK
    except Exception:
        return _ERR
