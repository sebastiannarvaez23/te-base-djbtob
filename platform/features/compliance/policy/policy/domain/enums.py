from enum import Enum


class PolicyAudience(str, Enum):
    """Audiencia de la política: determina el prefijo MinIO."""

    CLIENT = 'client'  # usuarios de tenant → client/policies/
    ADMIN = 'admin'    # usuarios de plataforma → admin/policies/


class PolicySubjectType(str, Enum):
    """Tipo de firmante (debe alinearse con PolicyAudience)."""

    CLIENT = 'client'
    ADMIN = 'admin'


class PolicyCountryStatus(str, Enum):
    """Estado de una versión por país."""

    DRAFT = 'draft'          # editable; no firmable
    APPROVED = 'approved'    # materializada, aún no vigente
    PUBLISHED = 'published'  # vigente / firmable
    REVOKED = 'revoked'      # supersedida
