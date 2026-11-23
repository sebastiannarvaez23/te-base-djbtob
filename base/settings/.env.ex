DEBUG=
ENV=
SECRET_KEY=
DOMAIN_PLATFORM=

# Postgresql OLTP — contenedor Docker (wadb, django-tenants)
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

# Postgresql analytics / Data Warehouse (wadw)
# Defaults: same host/user/password as DB_*; only the database name differs.
# Init: docker/postgres/init-wadw.sh (first volume) or CREATE DATABASE wadw.
# DW_NAME=wadw
# DW_USER=
# DW_PASSWORD=
# DW_HOST=
# DW_PORT=
# DW_CONN_MAX_AGE=60

# Analytics / ETL (core/analytics) — docs/plan-datawarehouse
# ANALYTICS_ENABLED=true
# ANALYTICS_STORE=fake
# ANALYTICS_STORE=postgres

# Redis — contenedor Docker
REDIS_URL=

# MinIO — contenedor Docker
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_USE_SSL=

# Email — Resend (producción) con SMTP histórico como respaldo
# EMAIL_PROVIDER=smtp | resend | fake
# Producción: verificar base.local en Resend (SPF + DKIM) y:
#   EMAIL_PROVIDER=resend
#   RESEND_API_KEY=re_...
#   DEFAULT_FROM_EMAIL=Notificaciones de la base <notificaciones@base.local>
# EMAIL_SMTP_FALLBACK=true → si Resend no puede enviar, usa EMAIL_BACKEND
# (Gmail SMTP / el método anterior). Conserva EMAIL_HOST_* para ese camino.
EMAIL_PROVIDER=smtp
RESEND_API_KEY=
EMAIL_SMTP_FALLBACK=true
EMAIL_FROM_NAME=Notificaciones de la base
DEFAULT_FROM_EMAIL=Notificaciones de la base <notificaciones@base.local>
EMAIL_REPLY_TO=info@base.local
EMAIL_HOST=
EMAIL_PORT=
EMAIL_USE_TLS=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Onboarding & email-confirmation links — base URLs of the frontend
# pages that consume the magic-link tokens. The dispatcher appends
# ?token=<raw> on send. Override per environment so dev emails don't
# route confirmation traffic into the prod frontend.
#
# Note: base-client-web mounts auth screens under /security, so both URLs
# must include that prefix. Otherwise the SPA's catch-all redirects to
# /security/login and the token is dropped before the page can read it.
#
# Dev   : http://app.base.local:4110/security/<page>
# Prod  : https://<your-domain>/security/<page>
EMAIL_CFM_URL=http://app.base.local:4110/security/confirm-email
ONB_RESUME_URL=http://app.base.local:4110/security/onboarding/resume
PASSWORD_RESET_URL=http://app.base.local:4110/security/password-reset
USER_ACTIVATION_URL=http://app.base.local:4110/security/activate-account

# Celery — broker (DB 2) and redbeat schedule store (DB 3) on the same
# Redis instance as the caches. DB numbers are deliberately separate so
# a cache eviction never poisons the task queue or the Beat schedule.
# Defaults derive from REDIS_URL automatically; override only when
# pointing at a different Redis cluster.
CELERY_BROKER_URL=redis://127.0.0.1:3110/2
CELERY_REDBEAT_REDIS_URL=redis://127.0.0.1:3110/3

# Observability buffers (live logs ring). Dedicated DB so auth cache is
# never contended by log fan-out. IGNORE_EXCEPTIONS=True (best-effort).
# REDIS_OBSERVABILITY_URL=redis://127.0.0.1:3110/5
# LIVE_LOGS_ENABLED=true
# LIVE_LOGS_MIN_LEVEL=INFO
# LIVE_LOGS_CAPTURE_ASYNC=true

# ── IA / SLM nativo (docs/plan-ia Fase 0b) ───────────────────────────────────
# Kill-switch producto: AI_ENABLED=false → get_chat_model('local') lanza AI_006.
# Kill-switch infra: no levantar el profile `ai` → 0 RAM del modelo.
# AI_ENABLED=true
# AI_PROVIDER=fake
# AI_PROVIDER=local
# AI_RUNTIME_URL=http://127.0.0.1:3310
# AI_CHAT_MODEL=qwen2.5:1.5b
# AI_MAX_TOKENS=1024
# AI_TIMEOUT_SECONDS=60
# AI_MAX_CONCURRENT=1
# AI_API_KEY=

# ── Phase 4 — Neurana fiscal invoicing ───────────────────────────────────────
# local (default): keep base invoice numbers; no remote calls.
# neurana: POST ecosystem invoices after InvoiceIssued (Idempotency-Key=charge.id).
# INVOICING_PROVIDER=local
# NE_ECOSYSTEM_ENABLED=false
# NE_ECOSYSTEM_BASE_URL=http://api.neurana.local:8000
# NE_PRODUCT_CODE=base
# NE_PRODUCT_CLIENT_ID=base_dev
# Auth: private_key_jwt (Ed25519). Generate with `manage.py generate_ne_product_key`
# and register the printed JWK in Neurana (`register_product_key`). The client
# secret is only a fallback while Neurana keeps ECOSYSTEM_ALLOW_CLIENT_SECRET on.
# NE_PRODUCT_PRIVATE_KEY_FILE=../secrets/neurana/product.pem
# NE_PRODUCT_PRIVATE_KEY=
# NE_PRODUCT_CLIENT_SECRET=
# Plain http is accepted only for local hosts (localhost / *.local).
# NE_ALLOW_INSECURE_HTTP=true
# NE_CONNECT_TIMEOUT_SECONDS=2
# NE_READ_TIMEOUT_SECONDS=8
# NE_HTTP_MAX_RETRIES=2
# NE_BREAKER_FAILURE_THRESHOLD=5
# NE_BREAKER_COOLDOWN_SECONDS=30
# NE_BREAKER_MAX_COOLDOWN_SECONDS=300
# Webhooks: Ed25519 (v2) verified against Neurana's JWKS; HMAC v1 while allowed.
# Deuda DT-001 (docs/deuda-tecnica.md): NE_WEBHOOK_ALLOW_V1 and
# NE_PRODUCT_CLIENT_SECRET are transitional; switch off in the documented order.
# NE_ECOSYSTEM_JWKS_URL=http://api.neurana.local:8000/api/v1/ecosystem/.well-known/jwks.json
# NE_JWKS_CACHE_SECONDS=600
# NE_WEBHOOK_ALLOW_V1=true
# NE_WEBHOOK_SECRETS=dev-webhook-secret
# Fiscal outbox (Neurana down ⇒ invoices queue and retry for up to 72 h)
# FISCAL_OUTBOX_MAX_AGE_HOURS=72
# FISCAL_OUTBOX_RELAY_INTERVAL_SECONDS=30
# FISCAL_ALERT_PENDING_MINUTES=15
# NE_DEFAULT_TAX_CODES=IVA19
# NE_TAX_INCLUSIVE=true
# NE_DEFAULT_TAX_RATE=19
