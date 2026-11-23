"""Códigos de error — messaging."""
from enum import Enum


class EmailErrorCode(str, Enum):
    """Correo."""

    EMAIL_TEMPLATE_NOT_FOUND = 'EMAIL_001'  # Plantilla de correo no encontrada
    EMAIL_DUPLICATE_CODE     = 'EMAIL_002'  # Código de plantilla duplicado
    EMAIL_TEMPLATE_INACTIVE  = 'EMAIL_003'  # Plantilla de correo inactiva
    EMAIL_RENDER_ERROR       = 'EMAIL_004'  # Error al renderizar plantilla
    EMAIL_SEND_FAILED        = 'EMAIL_005'  # Error al enviar correo
    EMAIL_SENDER_NOT_FOUND   = 'EMAIL_006'  # Remitente no encontrado
    EMAIL_SENDER_DUPLICATE   = 'EMAIL_007'  # Código de remitente duplicado
    EMAIL_PROVIDER_UNAVAILABLE = 'EMAIL_008'  # Transporte de correo no configurado (Resend sin key, proveedor desconocido)


EMAIL_REGISTRY: dict[EmailErrorCode, dict] = {
    EmailErrorCode.EMAIL_TEMPLATE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Email template not found',
        'detail': 'The requested email template does not exist.',
    },
    EmailErrorCode.EMAIL_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate template code',
        'detail': 'An email template with that code already exists.',
    },
    EmailErrorCode.EMAIL_TEMPLATE_INACTIVE: {
        'http_status': 409,
        'message': 'Email template inactive',
        'detail': 'The email template is currently inactive and cannot be used for sending.',
    },
    EmailErrorCode.EMAIL_RENDER_ERROR: {
        'http_status': 500,
        'message': 'Template render error',
        'detail': 'An error occurred while rendering the email template.',
    },
    EmailErrorCode.EMAIL_SEND_FAILED: {
        'http_status': 500,
        'message': 'Email send failed',
        'detail': 'An error occurred while attempting to send the email.',
    },
    EmailErrorCode.EMAIL_SENDER_NOT_FOUND: {
        'http_status': 404,
        'message': 'Sender not found',
        'detail': 'The requested email sender does not exist.',
    },
    EmailErrorCode.EMAIL_SENDER_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate sender code',
        'detail': 'A sender with the given code already exists.',
    },
    EmailErrorCode.EMAIL_PROVIDER_UNAVAILABLE: {
        'http_status': 500,
        'message': 'Email provider unavailable',
        'detail': 'The email transport is not configured for this environment.',
    },
}


class DocumentErrorCode(str, Enum):
    """Plantillas de documento."""

    DOC_TEMPLATE_NOT_FOUND      = 'DOC_001'  # Plantilla de documento no encontrada
    DOC_DUPLICATE_CODE          = 'DOC_002'  # Código de plantilla de documento duplicado
    DOC_TEMPLATE_INACTIVE       = 'DOC_003'  # Plantilla inactiva
    DOC_FORMAT_NOT_ALLOWED      = 'DOC_004'  # Formato solicitado no está en allowed_formats de la plantilla
    DOC_FORMAT_CONFIG_MISSING   = 'DOC_005'  # Falta configuración del formato en format_configs
    DOC_FORMAT_CONFIG_INVALID   = 'DOC_006'  # Configuración del formato malformada o inválida
    DOC_RENDERER_NOT_REGISTERED = 'DOC_007'  # No hay renderer registrado para el formato
    DOC_RENDER_FAILED           = 'DOC_008'  # Error durante el render
    DOC_NOT_STORABLE            = 'DOC_009'  # Se intenta persistir un documento de plantilla no almacenable
    DOC_STORAGE_PATH_INVALID    = 'DOC_010'  # storage_path_template inválido o con riesgo (path traversal, sin uniqueness)
    DOC_DEFAULT_FORMAT_MISMATCH = 'DOC_011'  # default_format no está en allowed_formats
    DOC_ALLOWED_FORMATS_EMPTY   = 'DOC_012'  # allowed_formats vacío


DOC_REGISTRY: dict[DocumentErrorCode, dict] = {
    DocumentErrorCode.DOC_TEMPLATE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Document template not found',
        'detail': 'The requested document template does not exist.',
    },
    DocumentErrorCode.DOC_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate document template code',
        'detail': 'A document template with that code already exists.',
    },
    DocumentErrorCode.DOC_TEMPLATE_INACTIVE: {
        'http_status': 400,
        'message': 'Document template inactive',
        'detail': 'The requested document template is inactive and cannot be used.',
    },
    DocumentErrorCode.DOC_FORMAT_NOT_ALLOWED: {
        'http_status': 400,
        'message': 'Format not allowed for template',
        'detail': "The requested format is not in the template's allowed_formats.",
    },
    DocumentErrorCode.DOC_FORMAT_CONFIG_MISSING: {
        'http_status': 400,
        'message': 'Format configuration missing',
        'detail': 'The template declares the format as allowed but no configuration exists for it.',
    },
    DocumentErrorCode.DOC_FORMAT_CONFIG_INVALID: {
        'http_status': 400,
        'message': 'Format configuration invalid',
        'detail': 'The configuration for the requested format is malformed.',
    },
    DocumentErrorCode.DOC_RENDERER_NOT_REGISTERED: {
        'http_status': 500,
        'message': 'Renderer not registered',
        'detail': 'No renderer is registered for the requested format.',
    },
    DocumentErrorCode.DOC_RENDER_FAILED: {
        'http_status': 500,
        'message': 'Render failed',
        'detail': 'An error occurred while rendering the document.',
    },
    DocumentErrorCode.DOC_NOT_STORABLE: {
        'http_status': 400,
        'message': 'Template not storable',
        'detail': 'This template is not configured for storage; persist=true is not allowed.',
    },
    DocumentErrorCode.DOC_STORAGE_PATH_INVALID: {
        'http_status': 400,
        'message': 'Storage path template invalid',
        'detail': 'The storage_path_template is missing uniqueness tokens or contains illegal segments.',
    },
    DocumentErrorCode.DOC_DEFAULT_FORMAT_MISMATCH: {
        'http_status': 400,
        'message': 'Default format mismatch',
        'detail': 'The default_format must be present in allowed_formats.',
    },
    DocumentErrorCode.DOC_ALLOWED_FORMATS_EMPTY: {
        'http_status': 400,
        'message': 'No allowed formats',
        'detail': 'The template must allow at least one format.',
    },
}


class NotificationErrorCode(str, Enum):
    """Notificaciones."""

    NOTIF_RESOURCE_TYPE_NOT_FOUND = 'NOTIF_001'  # Tipo de recurso compartible no encontrado
    NOTIF_RESOURCE_TYPE_DUPLICATE = 'NOTIF_002'  # Código de tipo de recurso duplicado
    NOTIF_RESOURCE_TYPE_INACTIVE  = 'NOTIF_003'  # Tipo de recurso inactivo (no compartible)
    NOTIF_INVALID_AUDIENCE        = 'NOTIF_004'  # Audiencia mal especificada para el alcance
    NOTIF_NOT_FOUND               = 'NOTIF_005'  # Notificación no encontrada para el usuario


NOTIF_REGISTRY: dict[NotificationErrorCode, dict] = {
    NotificationErrorCode.NOTIF_RESOURCE_TYPE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Resource type not found',
        'detail': 'The requested shareable resource type does not exist.',
    },
    NotificationErrorCode.NOTIF_RESOURCE_TYPE_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate resource type code',
        'detail': 'A shareable resource type with that code already exists.',
    },
    NotificationErrorCode.NOTIF_RESOURCE_TYPE_INACTIVE: {
        'http_status': 409,
        'message': 'Resource type inactive',
        'detail': 'This resource type is not enabled for sharing.',
    },
    NotificationErrorCode.NOTIF_INVALID_AUDIENCE: {
        'http_status': 400,
        'message': 'Invalid audience',
        'detail': 'The audience target does not match the selected scope.',
    },
    NotificationErrorCode.NOTIF_NOT_FOUND: {
        'http_status': 404,
        'message': 'Notification not found',
        'detail': 'The requested notification does not exist for this user.',
    },
}

__all__ = ['EmailErrorCode', 'DocumentErrorCode', 'NotificationErrorCode', 'EMAIL_REGISTRY', 'DOC_REGISTRY', 'NOTIF_REGISTRY']
