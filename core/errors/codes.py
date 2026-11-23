"""
core/errors/codes.py
────────────────────
Catálogo central de códigos de error de la aplicación.

Los miembros viven en ``core.errors.domains`` (una clase Enum por dominio).
Este módulo solo ensambla ``AppErrorCode`` y ``ERROR_REGISTRY``.

Formato de código: DOMINIO_NNN

Cada entrada del registro define:
  - http_status : Código HTTP que se retorna al cliente
  - message     : Título breve del error (inglés)
  - detail      : Descripción técnica del error (inglés)

El frontend usa ``error.code`` para mostrar mensajes localizados.
"""

from necore.ecosystem.errors import ECO_REGISTRY, EcoErrorCode

from core.errors.domains.access import (
    FUNC_REGISTRY,
    GRANT_REGISTRY,
    MFLT_REGISTRY,
    MOD_REGISTRY,
    PERM_REGISTRY,
    ROLE_REGISTRY,
    SEC_REGISTRY,
    SESS_REGISTRY,
    USER_REGISTRY,
    FuncErrorCode,
    GrantErrorCode,
    ModuleErrorCode,
    ModuleFilterErrorCode,
    SectionErrorCode,
    PermErrorCode,
    RoleErrorCode,
    SessionErrorCode,
    UserErrorCode,
)
from core.errors.domains.auth import AUTH_REGISTRY, AuthErrorCode
from core.errors.domains.billing import (
    INV_REGISTRY,
    PAY_REGISTRY,
    PROMO_REGISTRY,
    RFD_REGISTRY,
    SLIMIT_REGISTRY,
    CMP_REGISTRY,
    SUB_REGISTRY,
    ComplementErrorCode,
    InvoiceErrorCode,
    PaymentErrorCode,
    PromoErrorCode,
    RefundErrorCode,
    SubscriptionErrorCode,
    SubscriptionLimitErrorCode,
)
from core.errors.domains.compose import compose_error_code, compose_registry
from core.errors.domains.fiscal import FIS_REGISTRY, FisErrorCode
from core.errors.domains.configuration import (
    APARAM_REGISTRY,
    APTYPE_REGISTRY,
    FLAG_REGISTRY,
    LAND_REGISTRY,
    PARAM_REGISTRY,
    PTYPE_REGISTRY,
    TST_REGISTRY,
    AdminParameterErrorCode,
    AdminParameterTypeErrorCode,
    FlagErrorCode,
    LandingErrorCode,
    ParameterErrorCode,
    ParameterTypeErrorCode,
    TestimonialErrorCode,
)
from core.errors.domains.messaging import (
    DOC_REGISTRY,
    EMAIL_REGISTRY,
    NOTIF_REGISTRY,
    DocumentErrorCode,
    EmailErrorCode,
    NotificationErrorCode,
)
from core.errors.domains.handbook import HBK_REGISTRY, HandbookErrorCode
from core.errors.domains.compliance import POL_REGISTRY, PolicyErrorCode
from core.errors.domains.geography import GEO_REGISTRY, GeographyErrorCode
from core.errors.domains.platform import (
    AI_REGISTRY,
    INC_REGISTRY,
    INT_REGISTRY,
    SIGN_REGISTRY,
    SSES_REGISTRY,
    STR_REGISTRY,
    TASKMON_REGISTRY,
    AiErrorCode,
    IncidentErrorCode,
    IntegrationErrorCode,
    SigningErrorCode,
    StorageErrorCode,
    SupportSessionErrorCode,
    TaskMonitorErrorCode,
)
from core.errors.domains.system import (
    HTTP_REGISTRY,
    RL_REGISTRY,
    SRV_REGISTRY,
    VAL_REGISTRY,
    HttpErrorCode,
    RateLimitErrorCode,
    ServerErrorCode,
    ValidationErrorCode,
)
from core.errors.domains.tenant import (
    COMP_REGISTRY,
    ONB_REGISTRY,
    CompanyErrorCode,
    OnboardingErrorCode,
)

_DOMAIN_CODES = (
    AuthErrorCode,
    PermErrorCode,
    RoleErrorCode,
    SessionErrorCode,
    UserErrorCode,
    SectionErrorCode,
    ModuleErrorCode,
    FuncErrorCode,
    ModuleFilterErrorCode,
    GrantErrorCode,
    CompanyErrorCode,
    OnboardingErrorCode,
    SubscriptionErrorCode,
    ComplementErrorCode,
    RefundErrorCode,
    SubscriptionLimitErrorCode,
    InvoiceErrorCode,
    PromoErrorCode,
    PaymentErrorCode,
    EmailErrorCode,
    DocumentErrorCode,
    NotificationErrorCode,
    ParameterTypeErrorCode,
    ParameterErrorCode,
    AdminParameterTypeErrorCode,
    AdminParameterErrorCode,
    LandingErrorCode,
    TestimonialErrorCode,
    FlagErrorCode,
    StorageErrorCode,
    IncidentErrorCode,
    TaskMonitorErrorCode,
    SupportSessionErrorCode,
    HandbookErrorCode,
    PolicyErrorCode,
    GeographyErrorCode,
    AiErrorCode,
    SigningErrorCode,
    IntegrationErrorCode,
    EcoErrorCode,
    FisErrorCode,
    ValidationErrorCode,
    ServerErrorCode,
    RateLimitErrorCode,
    HttpErrorCode,
)

_DOMAIN_REGISTRIES = (
    AUTH_REGISTRY,
    PERM_REGISTRY,
    ROLE_REGISTRY,
    SESS_REGISTRY,
    USER_REGISTRY,
    SEC_REGISTRY,
    MOD_REGISTRY,
    FUNC_REGISTRY,
    MFLT_REGISTRY,
    GRANT_REGISTRY,
    COMP_REGISTRY,
    ONB_REGISTRY,
    SUB_REGISTRY,
    CMP_REGISTRY,
    RFD_REGISTRY,
    SLIMIT_REGISTRY,
    INV_REGISTRY,
    PROMO_REGISTRY,
    PAY_REGISTRY,
    EMAIL_REGISTRY,
    DOC_REGISTRY,
    NOTIF_REGISTRY,
    PTYPE_REGISTRY,
    PARAM_REGISTRY,
    APTYPE_REGISTRY,
    APARAM_REGISTRY,
    LAND_REGISTRY,
    TST_REGISTRY,
    FLAG_REGISTRY,
    STR_REGISTRY,
    INC_REGISTRY,
    TASKMON_REGISTRY,
    SSES_REGISTRY,
    HBK_REGISTRY,
    POL_REGISTRY,
    GEO_REGISTRY,
    AI_REGISTRY,
    SIGN_REGISTRY,
    INT_REGISTRY,
    ECO_REGISTRY,
    FIS_REGISTRY,
    VAL_REGISTRY,
    SRV_REGISTRY,
    RL_REGISTRY,
    HTTP_REGISTRY,
)

AppErrorCode = compose_error_code(
    'AppErrorCode',
    *_DOMAIN_CODES,
    module='core.errors.codes',
)

ERROR_REGISTRY: dict[AppErrorCode, dict] = compose_registry(
    AppErrorCode,
    *_DOMAIN_REGISTRIES,
)
