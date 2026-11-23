"""Códigos de error — configuration."""
from enum import Enum


class ParameterTypeErrorCode(str, Enum):
    """Tipos de parámetro."""

    PTYPE_NOT_FOUND      = 'PTYPE_001'  # Tipo de parámetro no encontrado
    PTYPE_DUPLICATE_CODE = 'PTYPE_002'  # Código de tipo de parámetro duplicado


PTYPE_REGISTRY: dict[ParameterTypeErrorCode, dict] = {
    ParameterTypeErrorCode.PTYPE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Parameter type not found',
        'detail': 'The requested parameter type does not exist.',
    },
    ParameterTypeErrorCode.PTYPE_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate parameter type code',
        'detail': 'A parameter type with that code already exists.',
    },
}


class ParameterErrorCode(str, Enum):
    """Parámetros."""

    PARAM_NOT_FOUND         = 'PARAM_001'  # Parámetro no encontrado
    PARAM_DUPLICATE_CODE    = 'PARAM_002'  # Código de parámetro duplicado
    PARAM_INVALID_DATA_TYPE = 'PARAM_003'  # Tipo de dato no soportado
    PARAM_INVALID_VALUE     = 'PARAM_004'  # Valor no compatible con el tipo de dato


PARAM_REGISTRY: dict[ParameterErrorCode, dict] = {
    ParameterErrorCode.PARAM_NOT_FOUND: {
        'http_status': 404,
        'message': 'Parameter not found',
        'detail': 'The requested parameter does not exist.',
    },
    ParameterErrorCode.PARAM_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate parameter code',
        'detail': 'A parameter with that code already exists.',
    },
    ParameterErrorCode.PARAM_INVALID_DATA_TYPE: {
        'http_status': 400,
        'message': 'Invalid data type',
        'detail': 'The specified data type is not supported. Valid types: STRING, INT, DECIMAL, BOOL, JSON.',
    },
    ParameterErrorCode.PARAM_INVALID_VALUE: {
        'http_status': 400,
        'message': 'Invalid parameter value',
        'detail': 'The value is not compatible with the declared data type.',
    },
}


class AdminParameterTypeErrorCode(str, Enum):
    """Admin-only parameter types."""

    APTYPE_NOT_FOUND = 'APTYPE_001'
    APTYPE_DUPLICATE_CODE = 'APTYPE_002'
    APTYPE_IN_USE = 'APTYPE_003'


APTYPE_REGISTRY: dict[AdminParameterTypeErrorCode, dict] = {
    AdminParameterTypeErrorCode.APTYPE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Admin parameter type not found',
        'detail': 'The requested admin parameter type does not exist.',
    },
    AdminParameterTypeErrorCode.APTYPE_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate admin parameter type code',
        'detail': 'An admin parameter type with that code already exists.',
    },
    AdminParameterTypeErrorCode.APTYPE_IN_USE: {
        'http_status': 409,
        'message': 'Admin parameter type in use',
        'detail': 'Remove or reassign admin parameters in this type before deleting it.',
    },
}


class AdminParameterErrorCode(str, Enum):
    """Admin-only parameters."""

    APARAM_NOT_FOUND = 'APARAM_001'
    APARAM_DUPLICATE_CODE = 'APARAM_002'
    APARAM_INVALID_DATA_TYPE = 'APARAM_003'
    APARAM_INVALID_VALUE = 'APARAM_004'


APARAM_REGISTRY: dict[AdminParameterErrorCode, dict] = {
    AdminParameterErrorCode.APARAM_NOT_FOUND: {
        'http_status': 404,
        'message': 'Admin parameter not found',
        'detail': 'The requested admin parameter does not exist.',
    },
    AdminParameterErrorCode.APARAM_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate admin parameter code',
        'detail': 'An admin parameter with that code already exists.',
    },
    AdminParameterErrorCode.APARAM_INVALID_DATA_TYPE: {
        'http_status': 400,
        'message': 'Invalid admin parameter data type',
        'detail': (
            'The specified data type is not supported. '
            'Valid types: STRING, INT, DECIMAL, BOOL, JSON.'
        ),
    },
    AdminParameterErrorCode.APARAM_INVALID_VALUE: {
        'http_status': 400,
        'message': 'Invalid admin parameter value',
        'detail': 'The value is not compatible with the declared data type.',
    },
}


class LandingErrorCode(str, Enum):
    """Landing."""

    LANDING_SECTION_NOT_FOUND = 'LAND_001'  # Sección de landing no encontrada
    LANDING_SECTION_UNKNOWN   = 'LAND_002'  # Key de sección desconocida


LAND_REGISTRY: dict[LandingErrorCode, dict] = {
    LandingErrorCode.LANDING_SECTION_NOT_FOUND: {
        'http_status': 404,
        'message': 'Landing section not found',
        'detail': 'The requested landing section does not exist.',
    },
    LandingErrorCode.LANDING_SECTION_UNKNOWN: {
        'http_status': 400,
        'message': 'Unknown landing section',
        'detail': 'The section key is not part of the landing catalog.',
    },
}


class TestimonialErrorCode(str, Enum):
    """Testimonials."""

    TESTIMONIAL_NOT_FOUND          = 'TST_001'  # Testimonio no encontrado
    TESTIMONIAL_AUTHOR_NOT_FOUND   = 'TST_002'  # Autor no encontrado
    TESTIMONIAL_DUPLICATE_AUTHOR   = 'TST_003'  # El usuario ya tiene un testimonio
    TESTIMONIAL_AUTHOR_INACTIVE    = 'TST_004'  # Autor inactivo
    TESTIMONIAL_SIGNATURE_REQUIRED = 'TST_005'  # Debe firmar el testimonio
    TESTIMONIAL_REPROMPT_NOT_ELIGIBLE = 'TST_006'  # Solo quienes ya calificaron


TST_REGISTRY: dict[TestimonialErrorCode, dict] = {
    TestimonialErrorCode.TESTIMONIAL_NOT_FOUND: {
        'http_status': 404,
        'message': 'Testimonial not found',
        'detail': 'The requested testimonial does not exist.',
    },
    TestimonialErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND: {
        'http_status': 404,
        'message': 'Testimonial author not found',
        'detail': 'The user who wrote the testimonial is not available.',
    },
    TestimonialErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR: {
        'http_status': 409,
        'message': 'Duplicate testimonial author',
        'detail': 'A testimonial for this user already exists.',
    },
    TestimonialErrorCode.TESTIMONIAL_AUTHOR_INACTIVE: {
        'http_status': 409,
        'message': 'Testimonial author inactive',
        'detail': 'The author account is inactive. Activate it or pick another user.',
    },
    TestimonialErrorCode.TESTIMONIAL_SIGNATURE_REQUIRED: {
        'http_status': 400,
        'message': 'Testimonial signature required',
        'detail': 'You must digitally sign the testimonial before sending it.',
    },
    TestimonialErrorCode.TESTIMONIAL_REPROMPT_NOT_ELIGIBLE: {
        'http_status': 400,
        'message': 'Testimonial reprompt not eligible',
        'detail': 'Only users who already submitted a rating can be asked again.',
    },
}


class FlagErrorCode(str, Enum):
    """Feature flags."""

    FLAG_NOT_FOUND       = 'FLAG_001'  # Feature flag no encontrada
    FLAG_DUPLICATE_KEY   = 'FLAG_002'  # Key de feature flag duplicada
    FLAG_INVALID_PAYLOAD = 'FLAG_003'  # Payload de flag inválido


FLAG_REGISTRY: dict[FlagErrorCode, dict] = {
    FlagErrorCode.FLAG_NOT_FOUND: {
        'http_status': 404,
        'message': 'Feature flag not found',
        'detail': 'The requested feature flag does not exist.',
    },
    FlagErrorCode.FLAG_DUPLICATE_KEY: {
        'http_status': 409,
        'message': 'Duplicate feature flag key',
        'detail': 'A feature flag with that key already exists.',
    },
    FlagErrorCode.FLAG_INVALID_PAYLOAD: {
        'http_status': 400,
        'message': 'Invalid feature flag payload',
        'detail': 'The feature flag payload failed validation.',
    },
}

__all__ = [
    'ParameterTypeErrorCode',
    'ParameterErrorCode',
    'AdminParameterTypeErrorCode',
    'AdminParameterErrorCode',
    'LandingErrorCode',
    'TestimonialErrorCode',
    'FlagErrorCode',
    'PTYPE_REGISTRY',
    'PARAM_REGISTRY',
    'APTYPE_REGISTRY',
    'APARAM_REGISTRY',
    'LAND_REGISTRY',
    'TST_REGISTRY',
    'FLAG_REGISTRY',
]
