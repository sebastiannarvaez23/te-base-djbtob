"""Constantes de dominio del handbook (audiencia, tipo, estado, storage)."""

from typing import FrozenSet


# ── Audiencias ───────────────────────────────────────────────────────────────

AUDIENCE_PUBLIC = 'public'
AUDIENCE_ADMIN = 'admin'
AUDIENCE_WMS = 'wms'

AUDIENCES: FrozenSet[str] = frozenset({
    AUDIENCE_PUBLIC,
    AUDIENCE_ADMIN,
    AUDIENCE_WMS,
})

# ── Tipos de contenido ───────────────────────────────────────────────────────

KIND_MANUAL = 'manual'
KIND_ARCHITECTURE = 'architecture'
KIND_TECHNICAL = 'technical'
KIND_PLAN = 'plan'
KIND_VISION = 'vision'
KIND_API = 'api'

KINDS: FrozenSet[str] = frozenset({
    KIND_MANUAL,
    KIND_ARCHITECTURE,
    KIND_TECHNICAL,
    KIND_PLAN,
    KIND_VISION,
    KIND_API,
})

# Método HTTP que documenta una página de tipo API (etiqueta en el sidebar).
HTTP_METHODS: FrozenSet[str] = frozenset({'GET', 'POST', 'PUT', 'PATCH', 'DELETE'})

# ── Publicación ──────────────────────────────────────────────────────────────

STATUS_DRAFT = 'draft'
STATUS_PUBLISHED = 'published'

STATUSES: FrozenSet[str] = frozenset({
    STATUS_DRAFT,
    STATUS_PUBLISHED,
})

# ── Locales ──────────────────────────────────────────────────────────────────

LOCALE_ES = 'es'
LOCALE_EN = 'en'
LOCALES: FrozenSet[str] = frozenset({LOCALE_ES, LOCALE_EN})
DEFAULT_LOCALE = LOCALE_ES

# ── Features de CMS (catálogo AdminFeature; no sembrar en migraciones) ──────
# Tecnológico redacta/envía; Administrador de Plataforma aprueba o deniega.

PROPOSE_FEATURE_KEY = 'admin.docs.propose'
APPROVE_FEATURE_KEY = 'admin.docs.approve'
# Staff del handbook (entra al CMS): proponer o aprobar.
MANAGE_FEATURE_KEY = PROPOSE_FEATURE_KEY

# ── Solicitud de cambio ──────────────────────────────────────────────────────

CHANGE_REQUEST_PENDING = 'pending'
CHANGE_REQUEST_APPROVED = 'approved'
CHANGE_REQUEST_REJECTED = 'rejected'

CHANGE_REQUEST_STATUSES: FrozenSet[str] = frozenset({
    CHANGE_REQUEST_PENDING,
    CHANGE_REQUEST_APPROVED,
    CHANGE_REQUEST_REJECTED,
})

REASON_MIN_LENGTH = 10
REASON_MAX_LENGTH = 2000

# ── MinIO ────────────────────────────────────────────────────────────────────
# Bytes en el bucket de documentos privado; metadatos y ACL viven en PostgreSQL.

HANDBOOK_OBJECT_PREFIX = 'handbook/'
HANDBOOK_MARKDOWN_CONTENT_TYPE = 'text/markdown; charset=utf-8'
HANDBOOK_MARKDOWN_MAX_BYTES = 2 * 1024 * 1024
HANDBOOK_BUCKET = 'base'
