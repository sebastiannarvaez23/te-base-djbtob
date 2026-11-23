from pathlib import Path
import environ

# ENVIRON CONF

env = environ.Env()
environ.Env.read_env(str(Path(__file__).resolve().parent / '.env'))

# ---

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# CORS / COOKIES — shared-root-domain multitenant
#
# Frontend fixed at http://app.base.local:4110 (never changes subdomain).
# Backend served from *.base.local:8100 via django-tenants host resolution.
# Auth cookie Domain=.base.local so it is shared across all subdomains.

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://([\w-]+\.)?base\.local:(4100|4110|4111|4120|4130|4140|4141|4142)$',
    r'^http://([\w-]+\.)?localhost:(4100|4110|4111|4120|4130|4140|4141|4142)$',
]
CORS_EXPOSE_HEADERS = ['Content-Type']
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-auth-context',
    'x-ui-context',
    'x-wa-frontend-logs',
]

CSRF_TRUSTED_ORIGINS = [
    'http://base.local:4100',
    'http://app.base.local:4110',
    'http://app.base.local:8100',
    'http://admin.base.local:4120',
    'http://docs.base.local:4130',
    'http://lib.base.local:4140',
    'http://prosandbox.base.local:4141',
    'http://localhost:4100',
    'http://localhost:4110',
    'http://localhost:4120',
    'http://localhost:4130',
    'http://localhost:4140',
    'http://localhost:4141',
]

# Base domain used to build tenant subdomains (e.g. `<schema>.base.local`)
# and to derive cookie domains (prefixed with `.` to cover all subdomains).
DOMAIN_PLATFORM = env.str('DOMAIN_PLATFORM', default='localhost')
_COOKIE_DOMAIN = f'.{DOMAIN_PLATFORM}' if DOMAIN_PLATFORM and DOMAIN_PLATFORM != 'localhost' else None

# Django session / CSRF cookies (not the primary auth in this project, but
# kept consistent for any forms-based admin).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
SESSION_COOKIE_DOMAIN = _COOKIE_DOMAIN
CSRF_COOKIE_DOMAIN = _COOKIE_DOMAIN
CSRF_COOKIE_SAMESITE = 'Lax'

# Frontend page that consumes the email-confirmation token (the dispatcher
# appends ?token=<raw> to it). Per-deployment, not per-tenant — env var.
# The base-client-web app mounts auth screens under /security, so the path
# must include that prefix or the link redirects to /security/login.
EMAIL_CFM_URL = env.str(
    'EMAIL_CFM_URL', default='http://app.base.local:4110/security/confirm-email',
)

# Frontend page that consumes the onboarding magic-link resume token.
# Same shape as EMAIL_CFM_URL: dispatcher appends ?token=<raw>.
ONB_RESUME_URL = env.str(
    'ONB_RESUME_URL', default='http://app.base.local:4110/security/onboarding/resume',
)

# Frontend page that consumes the password-recovery token. Same shape as
# EMAIL_CFM_URL: dispatcher appends ?token=<raw>. Short-lived link, so it
# is dropped on the SPA's /security/password-reset screen.
PASSWORD_RESET_URL = env.str(
    'PASSWORD_RESET_URL', default='http://app.base.local:4110/security/password-reset',
)

# Frontend page for invited company users to activate their account and set
# a password. Dispatcher appends ?token=<raw> (password-recovery token).
USER_ACTIVATION_URL = env.str(
    'USER_ACTIVATION_URL', default='http://app.base.local:4110/security/activate-account',
)

# ---

# APPS THIRD

THIRD_APPS = [
    'corsheaders',
    'drf_yasg',
    'rest_framework',
]

# -- TENANT CONF

MULTI_TENANT = True
TENANT_MODEL = "company.Company"
TENANT_DOMAIN_MODEL = "company.Domain"
AUTH_USER_MODEL = 'registration.User'
TENANT_PUBLIC_SCHEMA = 'public'
PUBLIC_SCHEMA_NAME = "public"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

# AnalyticsRouter must run before TenantSyncRouter: the latter returns
# False for any alias other than the tenant DB and would block wadw migrations.
DATABASE_ROUTERS = (
    'core.analytics.infrastructure.db_router.AnalyticsRouter',
    'django_tenants.routers.TenantSyncRouter',
)

SHARED_APPS = [
    # daphne debe ir primero para que ``runserver`` arranque en modo ASGI.
    'daphne',
    'channels',
    'django_tenants',
    # Utilidades transversales (comandos manage.py: syncerrors, etc.)
    'core.apps.CoreConfig',
    'platform.features.company.tenant.company',
    'platform.features.security.access.roles',
    'platform.features.security.identity.users',
    'platform.features.security.auth.auth',
    'platform.features.security.identity.identity',
    'platform.features.security.access.modules',
    'platform.features.security.access.sections',
    'platform.features.security.access.functionalities',
    'platform.features.billing.subscription.subscription',
    'platform.features.billing.subscription.subscription_module',
    'platform.features.billing.subscription.subscription_functionality',
    'platform.features.billing.complement.entitlement',
    'platform.features.billing.subscription.subscription_limit',
    'platform.features.billing.quota.quota_enforcement',
    'platform.features.billing.commerce.payment_method',
    'platform.features.billing.commerce.invoice',
    'platform.features.billing.commerce.fiscal_outbox',
    'platform.features.billing.commerce.payments',
    'platform.features.billing.commerce.refund',
    'platform.features.billing.commerce.promotion',
    'platform.features.communication.email.email_sender',
    'platform.features.communication.email.email_template',
    'platform.features.compliance.policy.policy',
    'platform.features.geography.location.location',
    'platform.features.geography.currency.currency',
    'platform.features.documents.document_template.document_template',
    'platform.features.configuration.parameters.parameter_type',
    'platform.features.configuration.parameters.parameter',
    'platform.features.configuration.admin_parameters.admin_parameter_type',
    'platform.features.configuration.admin_parameters.admin_parameter',
    'platform.features.configuration.landing.landing',
    'platform.features.configuration.landing.testimonial',
    'platform.features.configuration.assistant.assistant',
    'platform.features.configuration.ai.model_routing',
    'platform.features.configuration.ai.capability_control',
    'platform.features.configuration.ai.evals',
    'platform.features.release.feature_flag.feature_flag',
    'platform.features.integrations.connector_catalog.connector_catalog',
    # Notificaciones — parte pública (registro de tipos compartibles +
    # bandeja de salida del admin). El inbox per-tenant vive en TENANT_APPS.
    'platform.features.communication.messaging.inbox',
    'client.features.security.lifecycle.registration',
    'client.features.security.lifecycle.onboarding',
    'client.features.security.lifecycle.auth',
    'client.features.security.identity.identity',
    # Logging — shared (config y security logs viven en public schema)
    'client.features.logging.system.config',
    'client.features.logging.security.security',
    # Support — incidencias (administrativas, transversales a todas las empresas)
    'platform.features.support.incidents.incident',
    # Support — monitor de tareas automatizadas (Celery runs/steps)
    'platform.features.support.ops.task_monitor',
    # Support — stream de logs en vivo (handler + Redis ring + WS)
    'platform.features.support.ops.live_logs',
    # Support — live attention chat (admin ↔ tenant)
    'platform.features.support.sessions.session.apps.SupportSessionAppConfig',
    # Analytics — control plane + dims on wadw (router → DATABASES['analytics'])
    'platform.features.analytics.control.ctl',
    # Handbook — documentación de plataforma (schema público, ACL por audiencia)
    'handbook.features.docs.content.catalog',
    'handbook.features.docs.content.page',
    'handbook.features.docs.governance.change_request',
    'handbook.features.docs.governance.ingest',
    'rest_framework.authtoken',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.admin',
    'django.contrib.messages',
    'django.contrib.staticfiles',
] + THIRD_APPS

TENANT_APPS = [
    # Notificaciones — inbox particionado por tenant (la campanita).
    'client.features.communication.messaging.inbox',
    # Assistant — historial de chat por tenant
    'client.features.communication.assistant.chat',
    # Assistant — BYOK credentials (ciphertext en schema tenant)
    'client.features.communication.assistant.credentials',
    # Logging — tenant (logs operativos viven en schema del tenant)
    'client.features.logging.audit_trail.audit',
    'client.features.logging.ops.operations',
    'client.features.logging.ops.integration',
    'client.features.integrations.connections.profile',
    # Filtros avanzados por usuario y módulo
    'client.features.security.identity.module_filters',
    # Accesos otorgados por entidad
    'client.features.security.access.entity_grants',
]

# ---

INSTALLED_APPS = list(SHARED_APPS) + \
    [app for app in TENANT_APPS if app not in SHARED_APPS]

# SSL / TLS CONF

# SECURE_SSL_REDIRECT = False
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# if DEBUG:
#     INSTALLED_APPS += ['sslserver']
#     # Puedes configurar el puerto y las rutas que desees.
#     # En este ejemplo, se ejecuta en el puerto 8000 con SSL/TLS activado.
#     SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
#     SSLCERTIFICATE = '/path/to/cert.pem'
#     SSLKEY = '/path/to/key.pem'
# ---

# CACHE CONF
#
# default  → LocMemCache (throttling de DRF, sesiones, etc.)
#             Siempre funciona sin dependencias externas.
# access   → Redis (contadores de uso y caché de suscripción).
#             IGNORE_EXCEPTIONS=True: si Redis no está disponible,
#             retorna valores por defecto y el sistema degrada
#             gracefully a consultas directas a PostgreSQL.
#
# ⚠️ EVICCIÓN / DURABILIDAD (DB 0 'access'):
#   En este DB conviven claves con TTL corto (sub:*, usage:*:daily) y el
#   contador usage:*:lifetime SIN TTL. Si el servidor Redis se configura con
#   una política maxmemory 'allkeys-*' (LRU/LFU/random), el contador lifetime
#   es evictable como cualquier otra clave → sub-conteo silencioso del tope.
#   Recomendado en producción:
#     - Política de evicción 'volatile-lru' (solo desaloja claves CON TTL), o
#     - mover los contadores lifetime a un DB dedicado con 'noeviction'.
#   El código se auto-repara ante una pérdida (UsageStore.get_lifetime
#   re-siembra desde PostgreSQL en un miss para features con counter
#   registrado), pero eso solo cubre las que tienen counter; la política de
#   Redis es la primera línea de defensa.

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'access': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env.str('REDIS_URL', default='redis://127.0.0.1:3110/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
    },
    # Authentication cache.
    # Holds active access-token references and hashed refresh-token records.
    # IGNORE_EXCEPTIONS=False on purpose: if Redis is unreachable we want
    # auth requests to fail loud rather than silently bypass rotation.
    'auth': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env.str('REDIS_AUTH_URL', default=env.str('REDIS_URL', default='redis://127.0.0.1:3110/1')),
        'KEY_PREFIX': 'auth',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': False,
        },
    },
    # Observability buffers (live logs ring, etc.). Best-effort: never block
    # requests if Redis is down. Dedicated DB so auth traffic is not contended.
    'observability': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env.str(
            'REDIS_OBSERVABILITY_URL',
            default=env.str('REDIS_URL', default='redis://127.0.0.1:3110/5'),
        ),
        'KEY_PREFIX': 'obs',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
    },
}

# ── Auth cookie configuration ────────────────────────────────────────────────
# TOKEN_DURATION (access, minutes), REF_TOKEN_DURATION (refresh, days)
# and TIME_INACTIVITY (company-user idle, minutes; 0 disables) live as
# Parameters and are read at runtime by core.auth.jwt_service,
# core.auth.refresh_service and core.auth.inactivity.
AUTH_COOKIE_SAMESITE = env.str('AUTH_COOKIE_SAMESITE', default='Lax')
AUTH_COOKIE_DOMAIN = _COOKIE_DOMAIN

# Only honour X-Forwarded-For / geo headers when this process sits behind a
# trusted reverse proxy that overwrites them. Default off so clients cannot
# spoof login IP or the location printed in the 2FA email.
TRUST_X_FORWARDED_FOR = env.bool('TRUST_X_FORWARDED_FOR', default=False)
TRUST_GEO_HEADERS = env.bool('TRUST_GEO_HEADERS', default=False)

# ---

# DRF CONF

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'core.auth.cookie_authentication.JWTAccessAuthentication',
    ),
    'EXCEPTION_HANDLER': 'core.errors.handler.app_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
    },
}

# ---

# CELERY CONF
#
# Background tasks + Beat schedule. Broker and beat-lock storage both
# live in Redis but on dedicated DBs so an eviction in the cache layer
# never poisons the queue or the schedule.
#
#   DB 0 → 'access' cache       (existing)
#   DB 1 → 'auth'   cache       (existing)
#   DB 2 → Celery broker        (new)
#   DB 3 → redbeat schedule     (new)
#
# Workers and Beat are independent processes:
#   python manage.py runworkers
#   python manage.py runbeat
#
# In test runs CELERY_TASK_ALWAYS_EAGER is flipped on (see settings/local
# or per-test override) so tasks execute synchronously and the test
# suite never needs a real broker.

_REDIS_HOST_DEFAULT = env.str('REDIS_URL', default='redis://127.0.0.1:3110/0').rsplit('/', 1)[0]

CELERY_BROKER_URL = env.str(
    'CELERY_BROKER_URL', default=f'{_REDIS_HOST_DEFAULT}/2',
)
CELERY_RESULT_BACKEND = None        # fire-and-forget by default; flip per-task if needed
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Reliability: ack only after success so a worker crash mid-task
# re-delivers the message instead of silently dropping it. Prefetch=1
# stops a single worker from greedily reserving 100 tasks while it
# processes a slow one.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Hard ceilings: a runaway query must not pin a worker forever.
CELERY_TASK_TIME_LIMIT = 60 * 30
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 25

CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 60 * 60}

# Beat: redbeat keeps the schedule + a distributed lock in Redis, so
# running 2+ Beat replicas (HA) does not double-fire. ``django-celery-beat``
# would require manual leader election to achieve the same.
# BaseRedBeatScheduler re-acquires the lock instead of exiting when
# Redis drops ownership (Windows sleep, Docker pause, Redis restart).
CELERY_BEAT_SCHEDULER = 'core.tasks.scheduler.BaseRedBeatScheduler'
CELERY_REDBEAT_REDIS_URL = env.str(
    'CELERY_REDBEAT_REDIS_URL', default=f'{_REDIS_HOST_DEFAULT}/3',
)
# Must stay strictly above Beat's max_interval (default 300s). If the lock
# TTL equals max_interval, a delayed tick on Windows loses ownership.
CELERY_REDBEAT_LOCK_TIMEOUT = 60 * 10

# Interval must be bound before ``build_beat_schedule``: the schedule
# builder must not read ``django.conf.settings`` during this import.
FISCAL_OUTBOX_RELAY_INTERVAL_SECONDS = env.float('FISCAL_OUTBOX_RELAY_INTERVAL_SECONDS', default=30.0)

from core.tasks.schedules import build_beat_schedule  # noqa: E402

CELERY_BEAT_SCHEDULE = build_beat_schedule(
    fiscal_relay_interval=FISCAL_OUTBOX_RELAY_INTERVAL_SECONDS,
)
BEAT_SCHEDULE = CELERY_BEAT_SCHEDULE  # alias used by a few imports/tests


# ---

# LOGGING CONF
#
# Tres canales independientes con rotación de archivos (ConcurrentRotatingFileHandler
# para evitar WinError 32 cuando varios procesos abren el mismo .log):
#   app.security → logs/security.log  (auth, permisos)
#   app.errors   → logs/errors.log    (errores de negocio y servidor)
#   app.api      → logs/app.log       (info general de requests)
#
# En desarrollo también se emite todo por consola.
# En producción la consola solo muestra WARNING+.

_LOGS_DIR = BASE_DIR.parent / 'logs'
_LOGS_DIR.mkdir(exist_ok=True)

# ── Trazabilidad de request/response (RequestLoggingMiddleware) ──────────
#
# Los defaults derivan de DEBUG: con DEBUG=True se muestra todo (bodies +
# trazas por capa); con DEBUG=False se sigue la practica de un SaaS (solo el
# sobre request/response, sin payloads). Cada valor puede forzarse por
# variable de entorno si se necesita un caso puntual.
#
# REQUEST_LOG_BODIES : loguea el body del request y de la respuesta en linea.
#     Verboso — util en dev, NO recomendado en prod (llena disco / PII).
# REQUEST_LOG_LEVEL  : nivel de consola, requests.log y logs por tenant.
#     En DEBUG se muestran ademas las trazas por capa (@trace_layer) en archivos.
#     El anillo de incidencias captura esas trazas siempre (handler DEBUG).
# REQUEST_LOG_SKIP_PATHS : prefijos de ruta que no se loguean (health checks,
#     assets, polling ruidoso).
REQUEST_LOG_BODIES = env.bool('REQUEST_LOG_BODIES', default=DEBUG)
REQUEST_LOG_LEVEL = env.str(
    'REQUEST_LOG_LEVEL', default='DEBUG' if DEBUG else 'INFO',
).upper()
REQUEST_LOG_SKIP_PATHS = env.list(
    'REQUEST_LOG_SKIP_PATHS',
    default=['/static/', '/media/', '/favicon.ico', '/health', '/healthz'],
)

# ── Logs por empresa (tenant) ────────────────────────────────────────────
# Cada peticion de un tenant (schema != 'public') deja copia de sus logs en
# logs/tenants/<schema>/<YYYY-MM-DD>.log (un archivo por dia). Las peticiones
# del schema publico (admin/landing) no generan carpeta.
TENANT_LOG_ENABLED = env.bool('TENANT_LOG_ENABLED', default=True)
TENANT_LOGS_DIR = str(_LOGS_DIR / 'tenants')
_TENANT_HANDLERS = ['tenant_file'] if TENANT_LOG_ENABLED else []
# Días de retención por defecto para los logs por empresa cuando aún no existe
# una fila 'tenant' en LogConfiguration (el admin puede sobreescribirla).
TENANT_LOG_RETENTION_DAYS = env.int('TENANT_LOG_RETENTION_DAYS', default=90)

# ── Sistema de incidencias ───────────────────────────────────────────────
# Captura por sesión de las últimas N peticiones (Solicitud + Proceso interno
# + Respuesta) en Redis, disponibles para documentar una incidencia cuando el
# usuario reporta un error 500. Ver .pendings/ADM_INCIDENCIAS.md.
INCIDENT_CAPTURE_ENABLED = env.bool('INCIDENT_CAPTURE_ENABLED', default=True)
INCIDENT_RING_SIZE = env.int('INCIDENT_RING_SIZE', default=10)
# Pedidos: reserva ACID sobre inventory_balances.StockBalance (False → stub ORD_009).
ORDERS_USE_STOCK_BALANCES = env.bool('ORDERS_USE_STOCK_BALANCES', default=True)
INCIDENT_TXN_TTL_SECONDS = env.int('INCIDENT_TXN_TTL_SECONDS', default=3600)
INCIDENT_DRAFT_TTL_SECONDS = env.int('INCIDENT_DRAFT_TTL_SECONDS', default=3600)
REFERENCE_IMPORT_DRAFT_TTL_SECONDS = env.int('REFERENCE_IMPORT_DRAFT_TTL_SECONDS', default=3600)
REFERENCE_IMPORT_MAX_ROWS = env.int('REFERENCE_IMPORT_MAX_ROWS', default=5000)
REFERENCE_IMPORT_MAX_BYTES = env.int('REFERENCE_IMPORT_MAX_BYTES', default=5 * 1024 * 1024)
ORDER_IMPORT_DRAFT_TTL_SECONDS = env.int('ORDER_IMPORT_DRAFT_TTL_SECONDS', default=3600)
ORDER_IMPORT_MAX_ROWS = env.int('ORDER_IMPORT_MAX_ROWS', default=5000)
ORDER_IMPORT_MAX_BYTES = env.int('ORDER_IMPORT_MAX_BYTES', default=5 * 1024 * 1024)
INCIDENT_ENTRY_MAX_BYTES = env.int('INCIDENT_ENTRY_MAX_BYTES', default=16384)
INCIDENT_MAX_LOGS_PER_TXN = env.int('INCIDENT_MAX_LOGS_PER_TXN', default=200)
# URL que el front invoca para reportar la incidencia asociada a un 500.
INCIDENT_REPORT_URL = env.str('INCIDENT_REPORT_URL', default='/api/v1/incidents/report/')
# Si True, el push de la transacción al anillo se hace en un hilo daemon para
# no sumar el RTT de Redis a la latencia del request (mide ~1-3ms en local).
# Default False: síncrono, preserva el orden estricto por sesión.
INCIDENT_CAPTURE_ASYNC = env.bool('INCIDENT_CAPTURE_ASYNC', default=False)
# Fallos finales de tareas Celery → incidencia admin (solo logs app.tasks).
INCIDENT_TASK_FAILURE_ENABLED = env.bool('INCIDENT_TASK_FAILURE_ENABLED', default=True)
# Días de retención de incidencias cerradas/resueltas/descartadas (purga).
INCIDENT_RETENTION_DAYS = env.int('INCIDENT_RETENTION_DAYS', default=180)
# ── Live logs (admin support stream) ─────────────────────────────────────
# Opt-in via env in prod; default on for local admin tooling but MIN_LEVEL=INFO
# so DEBUG layer traces do not flood Redis/WS. Fan-out is async by default so
# Redis/Channels RTT stays off the request thread.
LIVE_LOGS_ENABLED = env.bool('LIVE_LOGS_ENABLED', default=True)
LIVE_LOGS_RING_SIZE = env.int('LIVE_LOGS_RING_SIZE', default=500)
LIVE_LOGS_RING_TTL_SECONDS = env.int('LIVE_LOGS_RING_TTL_SECONDS', default=3600)
LIVE_LOGS_MAX_MESSAGE_CHARS = env.int('LIVE_LOGS_MAX_MESSAGE_CHARS', default=2000)
LIVE_LOGS_MIN_LEVEL = env.str('LIVE_LOGS_MIN_LEVEL', default='INFO')
LIVE_LOGS_CAPTURE_ASYNC = env.bool('LIVE_LOGS_CAPTURE_ASYNC', default=True)
# Live-logs se engancha en AppConfig.ready() (stream_attach), no en dictConfig:
# el handler vive bajo platform.features… y configure_logging corre antes de
# popular apps → import falla en pytest / cold boot.
_INCIDENT_HANDLERS = ['incident_buffer'] if INCIDENT_CAPTURE_ENABLED else []
_TASK_INCIDENT_HANDLERS = (
    ['task_incident_buffer']
    if INCIDENT_CAPTURE_ENABLED and INCIDENT_TASK_FAILURE_ENABLED
    else []
)
# ── Promociones — compra pública (Fase 5) ────────────────────────────────────
PROMO_PUBLIC_CURRENCY = env.str('PROMO_PUBLIC_CURRENCY', default='USD')
PROMO_PUBLIC_REDEEM_MONTHS = env.int('PROMO_PUBLIC_REDEEM_MONTHS', default=12)
PROMO_PUBLIC_BILLING_COMPANY_ID = env.str('PROMO_PUBLIC_BILLING_COMPANY_ID', default='')
PROMO_GIFT_CATALOG_JSON = env.str('PROMO_GIFT_CATALOG_JSON', default='')
CLIENT_APP_URL = env.str('CLIENT_APP_URL', default='http://localhost:4110')
PLATFORM_SUPPORT_EMAIL = env.str('PLATFORM_SUPPORT_EMAIL', default='soporte@base.local')

# Políticas client obligatorias tras login (códigos Policy.code, mayúsculas).
# Vacío ⇒ no hay gate. Ampliar la lista para exigir más documentos publicados.
# Ver platform.features.compliance.policy.policy.domain.required_codes.
CLIENT_LOGIN_REQUIRED_POLICY_CODES = env.list(
    'CLIENT_LOGIN_REQUIRED_POLICY_CODES',
    default=['PRIVACY-POLICY', 'TERMS-AND-CONDITIONS'],
)

# ── Inteligencia Artificial (core/ai) ────────────────────────────────────────
# Módulo transversal de IA (puertos/adaptadores). Ver docs/plan-ia/ (FASE 0 / 0b).
# Default seguro: 'fake' (sin runtime). Camino del chat: AI_PROVIDER=local +
# docker compose --profile ai. 'anthropic' es opcional (no camino crítico).
# Release flags: 'django' (BD pública + caché) | 'fake' (memoria, tests)
FLAG_STORE = env.str('FLAG_STORE', default='django')

AI_ENABLED = env.bool('AI_ENABLED', default=True)
AI_PROVIDER = env.str('AI_PROVIDER', default='fake')  # 'fake' | 'local' | 'anthropic' | 'openai'
AI_EMBEDDING_PROVIDER = env.str('AI_EMBEDDING_PROVIDER', default='fake')
AI_DOCUMENT_PROVIDER = env.str('AI_DOCUMENT_PROVIDER', default='fake')
# Cubo 4 (OR) y cubo 3 (ML) — kill-switches y factory provider (hoy solo fake).
OR_ENABLED = env.bool('OR_ENABLED', default=True)
OR_PROVIDER = env.str('OR_PROVIDER', default='fake')
ML_ENABLED = env.bool('ML_ENABLED', default=True)
ML_PROVIDER = env.str('ML_PROVIDER', default='fake')
AI_API_KEY = env.str('AI_API_KEY', default='')
OPENAI_API_KEY = env.str('OPENAI_API_KEY', default='')
# Id del modelo: en local → tag Ollama (qwen2.5:1.5b); anthropic/openai → id cloud.
AI_CHAT_MODEL = env.str('AI_CHAT_MODEL', default='qwen2.5:1.5b')
AI_RUNTIME_URL = env.str('AI_RUNTIME_URL', default='http://127.0.0.1:3310')
AI_OPENAI_BASE_URL = env.str('AI_OPENAI_BASE_URL', default='https://api.openai.com')
AI_MAX_TOKENS = env.int('AI_MAX_TOKENS', default=1024)
AI_TIMEOUT_SECONDS = env.float('AI_TIMEOUT_SECONDS', default=60.0)
# Inferencias simultáneas hacia el runtime (protege CPU/RAM del host).
AI_MAX_CONCURRENT = env.int('AI_MAX_CONCURRENT', default=1)
# Enmascara secretos en el prompt antes de enviarlo al runtime/proveedor.
AI_REDACT_PROMPTS = env.bool('AI_REDACT_PROMPTS', default=True)
# Caché de completions deterministas (temperature=0) en Redis. Off por defecto.
AI_CACHE_ENABLED = env.bool('AI_CACHE_ENABLED', default=False)
AI_CACHE_TTL_SECONDS = env.int('AI_CACHE_TTL_SECONDS', default=3600)
# Tabla de precios por 1M tokens (FinOps; útil sobre todo con proveedores de pago),
# formato: {'<provider>:<model>': {'input': <usd>, 'output': <usd>}}.
AI_PRICING = env.json('AI_PRICING', default={})
# Tope de coste estimado USD por ventana horaria (Redis). Vacío = sin tope.
AI_HOURLY_BUDGET_USD = env.str('AI_HOURLY_BUDGET_USD', default='')

# ── Firma digital (core/signing) ─────────────────────────────────────────────
# Hash SHA-256 + sello HMAC genérico (políticas/acuerdos lo reutilizan después).
# En producción define SIGNING_SECRET_KEY dedicado; si está vacío se usa SECRET_KEY.
SIGNING_SECRET_KEY = env.str('SIGNING_SECRET_KEY', default='')
SIGNING_ALGORITHM = env.str('SIGNING_ALGORITHM', default='hmac-sha256-v1')

# ── Integraciones (core/integrations) ────────────────────────────────────────
# Módulo transversal de integraciones con ERPs y sistemas externos.
# Ver docs/plan-integrations/ (FASE 1).
INTEGRATIONS_ENABLED = env.bool('INTEGRATIONS_ENABLED', default=True)
INTEGRATIONS_SECRET_KEY = env.str('INTEGRATIONS_SECRET_KEY', default='')
INTEGRATIONS_DEFAULT_TIMEOUT_SECONDS = env.float('INTEGRATIONS_DEFAULT_TIMEOUT_SECONDS', default=30.0)
INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD = env.int('INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD', default=5)
# 'encrypted' (AES-GCM en memoria/BD) | 'fake' (tests)
INTEGRATIONS_SECRET_STORE = env.str('INTEGRATIONS_SECRET_STORE', default='encrypted')
# 'redis' | 'memory' (tests unitarios sin Redis)
INTEGRATIONS_IDEMPOTENCY_STORE = env.str('INTEGRATIONS_IDEMPOTENCY_STORE', default='redis')
INTEGRATIONS_ALLOW_PROSANDBOX = env.bool('INTEGRATIONS_ALLOW_PROSANDBOX', default=False)

# ── Analytics / Data Warehouse (core/analytics) ───────────────────────────────
# Ver docs/plan-datawarehouse/ (FASE 1). Safe default: store fake (sin DML wadw).
ANALYTICS_ENABLED = env.bool('ANALYTICS_ENABLED', default=True)
# 'fake' (tests / safe) | 'postgres' (Fase 2+ DML real en wadw)
ANALYTICS_STORE = env.str('ANALYTICS_STORE', default='fake')

# ── Integration Application OAuth (apps externas → base API) ─────────────
# Plano de auth dedicado (Bearer JWT), aislado de cookies admin/client.
INTEGRATION_JWT_SECRET = env.str('INTEGRATION_JWT_SECRET', default='')
INTEGRATION_TOKEN_TTL_SECONDS = env.int('INTEGRATION_TOKEN_TTL_SECONDS', default=3600)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format':  '[{asctime}] {levelname:<8} {name} | {message}',
            'style':   '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        # Consola: ERROR/CRITICAL en rojo, WARNING en amarillo (ANSI + colorama).
        'verbose_console': {
            '()': 'core.logging_formatters.ColoredConsoleFormatter',
            'format':  '[{asctime}] {levelname:<8} {name} | {message}',
            'style':   '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'structured': {
            'format':  (
                '[%(asctime)s] %(levelname)-8s %(name)s '
                'trace_id=%(trace_id)s error_code=%(error_code)s | %(message)s'
            ),
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'defaults': {'trace_id': '-', 'error_code': '-'},
        },
        # Traza de request/response: hora + trace_id + mensaje en linea.
        'request': {
            'format':  '[%(asctime)s] %(levelname)-8s trace_id=%(trace_id)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'defaults': {'trace_id': '-'},
        },
        'request_console': {
            '()': 'core.logging_formatters.ColoredConsoleFormatter',
            'format':  '[%(asctime)s] %(levelname)-8s trace_id=%(trace_id)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'defaults': {'trace_id': '-'},
        },
        'simple': {
            'format':  '{levelname} {message}',
            'style':   '{',
        },
    },

    'filters': {
        'debug_only': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'structured_defaults': {
            '()': 'core.logging_filters.StructuredDefaultsFilter',
        },
    },

    'handlers': {
        # Consola completa (solo en DEBUG)
        'console_debug': {
            'level':     'DEBUG',
            'class':     'logging.StreamHandler',
            'formatter': 'verbose_console',
            'filters':   ['debug_only'],
        },
        # Consola de errores (siempre activa)
        'console_errors': {
            'level':     'WARNING',
            'class':     'logging.StreamHandler',
            'formatter': 'verbose_console',
        },
        # Archivo: tráfico general de la API
        # ConcurrentRotatingFileHandler: evita WinError 32 al rotar con
        # runserver multi-proceso / varios workers abriendo el mismo archivo.
        'file_app': {
            'level':       'INFO',
            'class':       'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename':    str(_LOGS_DIR / 'app.log'),
            'maxBytes':    10 * 1024 * 1024,   # 10 MB
            'backupCount': 10,
            'formatter':   'verbose',
            'encoding':    'utf-8',
        },
        # Archivo: eventos de seguridad (auth/permisos) — retención extendida
        'file_security': {
            'level':       'WARNING',
            'class':       'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename':    str(_LOGS_DIR / 'security.log'),
            'maxBytes':    10 * 1024 * 1024,
            'backupCount': 20,
            'formatter':   'structured',
            'filters':     ['structured_defaults'],
            'encoding':    'utf-8',
        },
        # Archivo: errores de aplicación y servidor
        'file_errors': {
            'level':       'ERROR',
            'class':       'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename':    str(_LOGS_DIR / 'errors.log'),
            'maxBytes':    10 * 1024 * 1024,
            'backupCount': 10,
            'formatter':   'structured',
            'filters':     ['structured_defaults'],
            'encoding':    'utf-8',
        },
        # Consola de trazas request/response — SIEMPRE activa (no depende de DEBUG).
        # Bufferiza por request y vuelca el bloque al cerrar (sin intercalado).
        # El nivel de archivo/consola lo fija REQUEST_LOG_LEVEL; el anillo
        # (incident_buffer) sigue en DEBUG para capturar el proceso interno.
        'console_request': {
            'level':     REQUEST_LOG_LEVEL,
            'class':     'core.logging_handlers.OrderedRequestConsoleHandler',
            'formatter': 'request_console',
            'filters':   ['structured_defaults'],
        },
        # Archivo: traza de request/response
        'file_request': {
            'level':       REQUEST_LOG_LEVEL,
            'class':       'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename':    str(_LOGS_DIR / 'requests.log'),
            'maxBytes':    10 * 1024 * 1024,
            'backupCount': 10,
            'formatter':   'request',
            'filters':     ['structured_defaults'],
            'encoding':    'utf-8',
        },
        # Archivo por empresa: logs/tenants/<schema>/<YYYY-MM-DD>.log
        'tenant_file': {
            'level':       REQUEST_LOG_LEVEL,
            'class':       'core.logging_handlers.TenantDailyFileHandler',
            'formatter':   'request',
            'filters':     ['structured_defaults'],
        },
        # Buffer en memoria de los logs internos de la petición (incidencias).
        'incident_buffer': {
            'level':       'DEBUG',
            'class':       'core.logging_handlers.BufferingLogHandler',
            'formatter':   'request',
            'filters':     ['structured_defaults'],
        },
        'task_incident_buffer': {
            'level':       'DEBUG',
            'class':       'core.logging_handlers.TaskBufferingLogHandler',
            'formatter':   'verbose',
        },
    },

    'loggers': {
        # Tráfico general de la API
        'app.api': {
            'handlers':  ['console_debug', 'file_app'] + _TENANT_HANDLERS + _INCIDENT_HANDLERS,
            'level':     'INFO',
            'propagate': False,
        },
        # Traza request/response. El logger queda en DEBUG para que el anillo
        # reciba @trace_layer; consola/archivo/tenant filtran con REQUEST_LOG_LEVEL.
        'app.request': {
            'handlers':  ['console_request', 'file_request'] + _TENANT_HANDLERS + _INCIDENT_HANDLERS,
            'level':     'DEBUG',
            'propagate': False,
        },
        # Background tasks (Celery workers + Beat). Comparte el archivo
        # de tráfico general — el campo ``task_id`` en ``extra`` permite
        # filtrar/agrupar luego en el log aggregator.
        'app.tasks': {
            'handlers':  ['console_debug', 'console_errors', 'file_app'] + _TASK_INCIDENT_HANDLERS,
            'level':     'INFO',
            'propagate': False,
        },
        # Eventos de seguridad: login, tokens, permisos
        'app.security': {
            'handlers':  ['console_debug', 'console_errors', 'file_security'],
            'level':     'WARNING',
            'propagate': False,
        },
        # Uso y eventos de IA (tokens, costo, latencia, fallbacks) — core/ai
        'app.ai': {
            'handlers':  ['console_debug', 'console_errors', 'file_app'],
            'level':     'INFO',
            'propagate': False,
        },
        # Errores de negocio y servidor
        'app.errors': {
            'handlers':  ['console_debug', 'console_errors', 'file_app', 'file_errors'] + _TENANT_HANDLERS + _INCIDENT_HANDLERS,
            'level':     'INFO',
            'propagate': False,
        },
        # Django interno — solo errores relevantes
        'django': {
            'handlers':  ['console_errors', 'file_errors'],
            'level':     'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers':  ['console_errors', 'file_errors'],
            'level':     'ERROR',
            'propagate': False,
        },
    },
}

# ---

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'core.access.middleware.SubscriptionMiddleware',
    'core.middleware.RequestIDMiddleware',
    'core.middleware.RequestLoggingMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    # Tras CORS: un 403 temprano sin headers CORS llega vacío al navegador (SPA :4110).
    'core.access.middleware.BillingRecoveryMiddleware',
    'core.access.catalog_middleware.CatalogAccessMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.ObservabilityActorMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'platform.features.company.tenant.company.middleware.CompanyAdminMiddleware',
]

# CORS_ALLOWED_ORIGINS / CORS_ALLOWED_ORIGIN_REGEXES are defined at the top
# of this file (shared-root-domain multitenant block). Do not duplicate here.

ROOT_URLCONF = 'base.urls'
PUBLIC_SCHEMA_URLCONF = 'base.urls_public'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.debug',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'base.wsgi.application'
ASGI_APPLICATION = 'base.asgi.application'


# CHANNELS / REALTIME
#
# Channel layer sobre Redis para fan-out de WebSockets entre procesos
# (workers Celery → consumidores). Usa una DB dedicada (4) para no
# colisionar con cache (0/1), broker Celery (2) ni redbeat (3).
#
#   DB 4 → channels group layer
#
CHANNELS_REDIS_URL = env.str('CHANNELS_REDIS_URL', default=f'{_REDIS_HOST_DEFAULT}/4')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [CHANNELS_REDIS_URL],
        },
    },
}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Email ─────────────────────────────────────────────────────────────────────

# ── MinIO Storage ─────────────────────────────────────────────────────────────

MINIO_ENDPOINT   = env.str('MINIO_ENDPOINT',   default='127.0.0.1:3210')
MINIO_ACCESS_KEY = env.str('MINIO_ACCESS_KEY', default='')
MINIO_SECRET_KEY = env.str('MINIO_SECRET_KEY', default='')
MINIO_USE_SSL    = env.bool('MINIO_USE_SSL',   default=False)

# Browser-facing base URL for publicly-readable objects (e.g. profile pictures).
# Defaults to the MinIO endpoint; override in prod if MinIO is served behind a
# different public host/CDN. No trailing slash.
MINIO_PUBLIC_URL = env.str(
    'MINIO_PUBLIC_URL',
    default=f"{'https' if MINIO_USE_SSL else 'http'}://{MINIO_ENDPOINT}",
).rstrip('/')

# ── Document generation storage ──────────────────────────────────────────────

# Default bucket used when DocumentTemplate.storage_bucket is empty.
DOCUMENTS_DEFAULT_BUCKET        = env.str('DOCUMENTS_DEFAULT_BUCKET', default='documents')
# TTL for the signed URLs returned to the frontend after a storable render.
DOCUMENTS_SIGNED_URL_TTL_SECONDS = env.int('DOCUMENTS_SIGNED_URL_TTL_SECONDS', default=600)

# Fallback recipient for invoice PDFs when no explicit email is provided in
# the payment metadata. Leave empty to disable auto-send.
INVOICE_FALLBACK_RECIPIENT      = env.str('INVOICE_FALLBACK_RECIPIENT', default='')
# Seller entity printed on the invoice PDF (SaaS billing party).
INVOICE_SELLER_NAME             = env.str('INVOICE_SELLER_NAME', default='BASE SAS')
INVOICE_SELLER_TAX_ID           = env.str('INVOICE_SELLER_TAX_ID', default='901.234.567-8')
INVOICE_SELLER_ADDRESS          = env.str('INVOICE_SELLER_ADDRESS', default='Calle 100 #15-25')
INVOICE_SELLER_CITY             = env.str('INVOICE_SELLER_CITY', default='Cali, Valle del Cauca, Colombia')
# Default currency label when the invoice row has none (legacy rows).
INVOICE_DEFAULT_CURRENCY        = env.str('INVOICE_DEFAULT_CURRENCY', default='USD')

# Phase 4 — Neurana fiscal invoicing (default local = no remote calls).
INVOICING_PROVIDER = env.str('INVOICING_PROVIDER', default='local')
NE_ECOSYSTEM_ENABLED = env.bool('NE_ECOSYSTEM_ENABLED', default=False)
NE_ECOSYSTEM_BASE_URL = env.str('NE_ECOSYSTEM_BASE_URL', default='http://api.neurana.local:8000')
NE_PRODUCT_CODE = env.str('NE_PRODUCT_CODE', default='base')
NE_PRODUCT_CLIENT_ID = env.str('NE_PRODUCT_CLIENT_ID', default='')
# Deuda DT-001 (docs/deuda-tecnica.md): legacy client_secret auth; leave empty
# once the product key is registered in Neurana.
NE_PRODUCT_CLIENT_SECRET = env.str('NE_PRODUCT_CLIENT_SECRET', default='')
# private_key_jwt: Ed25519 key registered in Neurana (register_product_key).
# Takes precedence over NE_PRODUCT_CLIENT_SECRET when set.
NE_PRODUCT_PRIVATE_KEY = env.str('NE_PRODUCT_PRIVATE_KEY', default='')
NE_PRODUCT_PRIVATE_KEY_FILE = env.str(
    'NE_PRODUCT_PRIVATE_KEY_FILE',
    default=str(BASE_DIR.parent / 'secrets' / 'neurana' / 'product.pem'),
)
# Plain http only for local hosts (localhost / *.local); production must be https.
NE_ALLOW_INSECURE_HTTP = env.bool('NE_ALLOW_INSECURE_HTTP', default=DEBUG)
NE_CONNECT_TIMEOUT_SECONDS = env.float('NE_CONNECT_TIMEOUT_SECONDS', default=2.0)
NE_READ_TIMEOUT_SECONDS = env.float('NE_READ_TIMEOUT_SECONDS', default=8.0)
NE_HTTP_MAX_RETRIES = env.int('NE_HTTP_MAX_RETRIES', default=2)
NE_BREAKER_FAILURE_THRESHOLD = env.int('NE_BREAKER_FAILURE_THRESHOLD', default=5)
NE_BREAKER_COOLDOWN_SECONDS = env.float('NE_BREAKER_COOLDOWN_SECONDS', default=30.0)
NE_BREAKER_MAX_COOLDOWN_SECONDS = env.float('NE_BREAKER_MAX_COOLDOWN_SECONDS', default=300.0)
# Webhooks: Ed25519 v2 verified against Neurana's JWKS. Deuda DT-001
# (docs/deuda-tecnica.md): HMAC v1 is still accepted while NE_WEBHOOK_ALLOW_V1
# is on; switch it off (and empty NE_WEBHOOK_SECRETS) after Neurana stops
# signing v1.
NE_ECOSYSTEM_JWKS_URL = env.str(
    'NE_ECOSYSTEM_JWKS_URL',
    default=f'{NE_ECOSYSTEM_BASE_URL.rstrip("/")}/api/v1/ecosystem/.well-known/jwks.json',
)
NE_JWKS_CACHE_SECONDS = env.int('NE_JWKS_CACHE_SECONDS', default=600)
NE_WEBHOOK_SECRETS = env.list('NE_WEBHOOK_SECRETS', default=[])
NE_WEBHOOK_ALLOW_V1 = env.bool('NE_WEBHOOK_ALLOW_V1', default=True)
# Fiscal outbox relay: give up (dead letter + bell alert) after this age.
# ``FISCAL_OUTBOX_RELAY_INTERVAL_SECONDS`` is set with Celery Beat above.
FISCAL_OUTBOX_MAX_AGE_HOURS = env.float('FISCAL_OUTBOX_MAX_AGE_HOURS', default=72.0)
FISCAL_ALERT_PENDING_MINUTES = env.int('FISCAL_ALERT_PENDING_MINUTES', default=15)
# Neurana tax codes on base subscription lines (must exist in NE fiscal tax rates).
NE_DEFAULT_TAX_CODES = env.list('NE_DEFAULT_TAX_CODES', default=['IVA19'])
# base commercial totals are tax-inclusive; strip NE_DEFAULT_TAX_RATE before issue
# so Neurana re-adds VAT and the fiscal total matches the commercial amount.
NE_TAX_INCLUSIVE = env.bool('NE_TAX_INCLUSIVE', default=True)
NE_DEFAULT_TAX_RATE = env.str('NE_DEFAULT_TAX_RATE', default='19')

# ── Email (core/email — Resend en producción, SMTP como respaldo) ─────────────
# EMAIL_PROVIDER: smtp | resend | fake
# Producción: EMAIL_PROVIDER=resend + RESEND_API_KEY + dominio base.local
# verificado en Resend (SPF + DKIM). Si Resend falla o no hay API key,
# EMAIL_SMTP_FALLBACK=True usa el SMTP histórico (EMAIL_BACKEND / EMAIL_HOST).
EMAIL_PROVIDER      = env.str('EMAIL_PROVIDER', default='smtp')
EMAIL_APP_TAG       = env.str('EMAIL_APP_TAG', default='base')
RESEND_API_KEY      = env.str('RESEND_API_KEY', default='')
EMAIL_SMTP_FALLBACK = env.bool('EMAIL_SMTP_FALLBACK', default=True)
EMAIL_FROM_NAME     = env.str('EMAIL_FROM_NAME', default='Notificaciones de la base')
DEFAULT_FROM_EMAIL  = env.str('DEFAULT_FROM_EMAIL', default='Notificaciones de la base <notificaciones@base.local>')
EMAIL_REPLY_TO      = env.str('EMAIL_REPLY_TO', default='info@base.local')

EMAIL_BACKEND       = env.str('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST          = env.str('EMAIL_HOST', default='localhost')
EMAIL_PORT          = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS       = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER     = env.str('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD', default='')
