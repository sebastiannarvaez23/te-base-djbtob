from enum import Enum


class IdentityDocumentType(str, Enum):
    """Official identity document types accepted for a company administrator.

    Values are stored as a 2-letter code (DB check constraint + TextChoices).
    """

    CEDULA_CIUDADANIA = 'CC'
    CEDULA_EXTRANJERIA = 'CE'
    PASAPORTE = 'PA'

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)
