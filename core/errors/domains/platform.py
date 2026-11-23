"""Códigos de error — platform."""
from enum import Enum


class StorageErrorCode(str, Enum):
    """Almacenamiento."""

    STR_BUCKET_NOT_FOUND      = 'STR_001'  # Bucket no encontrado
    STR_FILE_NOT_FOUND        = 'STR_002'  # Archivo no encontrado en el bucket
    STR_UPLOAD_FAILED         = 'STR_003'  # Error al subir el archivo
    STR_DELETE_FAILED         = 'STR_004'  # Error al eliminar el archivo
    STR_BUCKET_ALREADY_EXISTS = 'STR_005'  # El bucket ya existe
    STR_PRESIGNED_URL_FAILED  = 'STR_006'  # Error al generar URL pre-firmada
    STR_SERVICE_ERROR         = 'STR_007'  # Error general del servicio de almacenamiento


STR_REGISTRY: dict[StorageErrorCode, dict] = {
    StorageErrorCode.STR_BUCKET_NOT_FOUND: {
        'http_status': 404,
        'message': 'Bucket not found',
        'detail': 'The requested storage bucket does not exist.',
    },
    StorageErrorCode.STR_FILE_NOT_FOUND: {
        'http_status': 404,
        'message': 'File not found',
        'detail': 'The requested file does not exist in the storage bucket.',
    },
    StorageErrorCode.STR_UPLOAD_FAILED: {
        'http_status': 500,
        'message': 'File upload failed',
        'detail': 'An error occurred while uploading the file to storage.',
    },
    StorageErrorCode.STR_DELETE_FAILED: {
        'http_status': 500,
        'message': 'File delete failed',
        'detail': 'An error occurred while deleting the file from storage.',
    },
    StorageErrorCode.STR_BUCKET_ALREADY_EXISTS: {
        'http_status': 409,
        'message': 'Bucket already exists',
        'detail': 'A bucket with that name already exists.',
    },
    StorageErrorCode.STR_PRESIGNED_URL_FAILED: {
        'http_status': 500,
        'message': 'Presigned URL generation failed',
        'detail': 'An error occurred while generating the presigned URL.',
    },
    StorageErrorCode.STR_SERVICE_ERROR: {
        'http_status': 500,
        'message': 'Storage service error',
        'detail': 'An unexpected error occurred in the storage service.',
    },
}


class IncidentErrorCode(str, Enum):
    """Incidencias."""

    INCIDENT_DRAFT_NOT_FOUND   = 'INC_001'  # Draft de incidencia inexistente o expirado
    INCIDENT_NOT_FOUND         = 'INC_002'  # Incidencia no encontrada
    INCIDENT_ASSIGNEE_REQUIRED = 'INC_003'  # Resolver/cerrar sin persona asignada
    INCIDENT_NOTES_REQUIRED    = 'INC_004'  # Resolver/cerrar sin notas del cambio
    INCIDENT_ATTACHMENTS_CLOSED  = 'INC_005'  # Adjuntar fuera de la ventana del reporter
    INCIDENT_ATTACHMENTS_LIMIT   = 'INC_006'  # Supera el máximo de adjuntos
    INCIDENT_ATTACHMENT_INVALID  = 'INC_007'  # Tipo/tamaño/contenido no permitido
    INCIDENT_ATTACHMENT_STORAGE  = 'INC_008'  # Almacenamiento de adjuntos falló


INC_REGISTRY: dict[IncidentErrorCode, dict] = {
    IncidentErrorCode.INCIDENT_DRAFT_NOT_FOUND: {
        'http_status': 410,
        'message': 'Incident not available',
        'detail': 'The incident is no longer available to report (invalid or expired link).',
    },
    IncidentErrorCode.INCIDENT_NOT_FOUND: {
        'http_status': 404,
        'message': 'Incident not found',
        'detail': 'The requested incident does not exist.',
    },
    IncidentErrorCode.INCIDENT_ASSIGNEE_REQUIRED: {
        'http_status': 409,
        'message': 'Incident has no assignee',
        'detail': 'Assign someone to handle this incident before resolving or closing it.',
    },
    IncidentErrorCode.INCIDENT_NOTES_REQUIRED: {
        'http_status': 400,
        'message': 'Resolution notes required',
        'detail': 'Write notes describing the change before resolving or closing the incident.',
    },
    IncidentErrorCode.INCIDENT_ATTACHMENTS_CLOSED: {
        'http_status': 409,
        'message': 'Attachments no longer accepted',
        'detail': 'Files can only be attached by the person who sent the report, right after sending it.',
    },
    IncidentErrorCode.INCIDENT_ATTACHMENTS_LIMIT: {
        'http_status': 400,
        'message': 'Too many attachments',
        'detail': 'A report accepts up to 5 files.',
    },
    IncidentErrorCode.INCIDENT_ATTACHMENT_INVALID: {
        'http_status': 400,
        'message': 'Attachment not allowed',
        'detail': 'Only JPG, PNG, WEBP or GIF images up to 8 MB and MP4 videos up to 20 MB are accepted.',
    },
    IncidentErrorCode.INCIDENT_ATTACHMENT_STORAGE: {
        'http_status': 503,
        'message': 'Attachments could not be saved',
        'detail': 'The files could not be stored right now. Try sending them again.',
    },
}


class TaskMonitorErrorCode(str, Enum):
    """Monitor de tareas."""

    TASKMON_TASK_NOT_FOUND = 'TASKMON_001'  # Tarea no está en el catálogo
    TASKMON_RUN_NOT_FOUND  = 'TASKMON_002'  # Ejecución de tarea no encontrada


TASKMON_REGISTRY: dict[TaskMonitorErrorCode, dict] = {
    TaskMonitorErrorCode.TASKMON_TASK_NOT_FOUND: {
        'http_status': 404,
        'message': 'Automated task not found',
        'detail': 'The requested automated task is not registered in the monitor catalog.',
    },
    TaskMonitorErrorCode.TASKMON_RUN_NOT_FOUND: {
        'http_status': 404,
        'message': 'Task run not found',
        'detail': 'The requested automated task execution does not exist.',
    },
}


class SupportSessionErrorCode(str, Enum):
    """Live support chat sessions."""

    SSES_NOT_FOUND = 'SSES_001'
    SSES_ALREADY_OPEN = 'SSES_002'
    SSES_ALREADY_ACCEPTED = 'SSES_003'
    SSES_INVALID_STATUS = 'SSES_004'
    SSES_NOT_ASSIGNED = 'SSES_005'
    SSES_AGENT_BUSY = 'SSES_006'
    SSES_INVALID_RATING = 'SSES_007'


SSES_REGISTRY: dict[SupportSessionErrorCode, dict] = {
    SupportSessionErrorCode.SSES_NOT_FOUND: {
        'http_status': 404,
        'message': 'Support session not found',
        'detail': 'That support conversation is no longer available.',
    },
    SupportSessionErrorCode.SSES_ALREADY_OPEN: {
        'http_status': 409,
        'message': 'Support session already open',
        'detail': 'You already have an open support conversation. Finish or cancel it before starting another.',
    },
    SupportSessionErrorCode.SSES_ALREADY_ACCEPTED: {
        'http_status': 409,
        'message': 'Support session already accepted',
        'detail': 'Another agent already accepted this support request.',
    },
    SupportSessionErrorCode.SSES_INVALID_STATUS: {
        'http_status': 409,
        'message': 'Support session status does not allow this action',
        'detail': 'This support conversation is not in a state that allows that step.',
    },
    SupportSessionErrorCode.SSES_NOT_ASSIGNED: {
        'http_status': 403,
        'message': 'Support session not assigned to you',
        'detail': 'Only the agent who accepted this conversation can continue it.',
    },
    SupportSessionErrorCode.SSES_AGENT_BUSY: {
        'http_status': 409,
        'message': 'Agent already in a support session',
        'detail': 'Finish your current support conversation before accepting another.',
    },
    SupportSessionErrorCode.SSES_INVALID_RATING: {
        'http_status': 400,
        'message': 'Invalid support rating',
        'detail': 'Choose a rating from 1 to 5 stars.',
    },
}


class AiErrorCode(str, Enum):
    """IA."""

    AI_PROVIDER_UNAVAILABLE   = 'AI_001'  # No hay proveedor de IA configurado o disponible
    AI_TIMEOUT                = 'AI_002'  # El proveedor no respondió dentro del tiempo límite
    AI_QUOTA_EXCEEDED         = 'AI_003'  # Cuota/tope de uso de IA excedido
    AI_INVALID_RESPONSE       = 'AI_004'  # El proveedor devolvió una respuesta inválida o vacía
    AI_PROVIDER_ERROR         = 'AI_005'  # Error al comunicarse con el proveedor de IA
    AI_DISABLED               = 'AI_006'  # La funcionalidad de IA está deshabilitada por configuración
    AI_CONVERSATION_NOT_FOUND = 'AI_007'  # Conversación del asistente no encontrada
    AI_UNKNOWN_TOOL           = 'AI_008'  # Tool del asistente no está en el catálogo
    AI_BUSY                   = 'AI_009'  # Otro turno del asistente ya está en curso
    AI_OR_DISABLED            = 'AI_010'  # Optimización (OR) deshabilitada por configuración
    AI_ML_DISABLED            = 'AI_011'  # ML predictivo deshabilitado por configuración
    AI_CREDENTIAL_NOT_FOUND   = 'AI_012'  # Credencial BYOK del tenant no encontrada
    AI_APPROVAL_DENIED        = 'AI_013'  # El operador denegó la acción del asistente


AI_REGISTRY: dict[AiErrorCode, dict] = {
    AiErrorCode.AI_PROVIDER_UNAVAILABLE: {
        'http_status': 503,
        'message': 'AI provider unavailable',
        'detail': 'No AI provider is configured or currently available. Check the AI_PROVIDER setting.',
    },
    AiErrorCode.AI_TIMEOUT: {
        'http_status': 504,
        'message': 'AI request timed out',
        'detail': 'The AI provider did not respond within the allowed time limit.',
    },
    AiErrorCode.AI_QUOTA_EXCEEDED: {
        'http_status': 429,
        'message': 'AI usage limit exceeded',
        'detail': 'The AI usage quota for this tenant or plan has been exceeded.',
    },
    AiErrorCode.AI_INVALID_RESPONSE: {
        'http_status': 502,
        'message': 'Invalid AI response',
        'detail': 'The AI provider returned an empty or malformed response.',
    },
    AiErrorCode.AI_PROVIDER_ERROR: {
        'http_status': 502,
        'message': 'AI provider error',
        'detail': 'An error occurred while communicating with the AI provider.',
    },
    AiErrorCode.AI_DISABLED: {
        'http_status': 503,
        'message': 'AI feature disabled',
        'detail': 'AI functionality is currently disabled by configuration.',
    },
    AiErrorCode.AI_CONVERSATION_NOT_FOUND: {
        'http_status': 404,
        'message': 'Assistant conversation not found',
        'detail': 'No assistant conversation matches this request. Open or start a chat from the assistant panel.',
    },
    AiErrorCode.AI_UNKNOWN_TOOL: {
        'http_status': 400,
        'message': 'Unknown assistant tool',
        'detail': 'The tool key is not part of the assistant catalog.',
    },
    AiErrorCode.AI_BUSY: {
        'http_status': 409,
        'message': 'Assistant turn in progress',
        'detail': 'Another assistant turn is already in progress on this connection.',
    },
    AiErrorCode.AI_OR_DISABLED: {
        'http_status': 503,
        'message': 'Optimization feature disabled',
        'detail': 'Warehouse optimization (OR) is currently disabled by configuration.',
    },
    AiErrorCode.AI_ML_DISABLED: {
        'http_status': 503,
        'message': 'Predictive ML feature disabled',
        'detail': 'Predictive ML is currently disabled by configuration.',
    },
    AiErrorCode.AI_CREDENTIAL_NOT_FOUND: {
        'http_status': 404,
        'message': 'AI provider credential not found',
        'detail': 'No matching BYOK credential was found. Add or activate a key in settings.',
    },
    AiErrorCode.AI_APPROVAL_DENIED: {
        'http_status': 403,
        'message': 'Assistant action denied',
        'detail': 'The operator denied the pending assistant action.',
    },
}


class SigningErrorCode(str, Enum):
    """Firma digital genérica (core/signing)."""

    SIGN_SECRET_MISSING        = 'SIGN_001'  # No hay secreto HMAC configurado
    SIGN_EMPTY_CONTENT         = 'SIGN_002'  # Contenido vacío al hashear
    SIGN_UNSUPPORTED_ALGORITHM = 'SIGN_003'  # Algoritmo de sello no soportado
    SIGN_INVALID_BINDING       = 'SIGN_004'  # Binding de documento o firmante inválido


SIGN_REGISTRY: dict[SigningErrorCode, dict] = {
    SigningErrorCode.SIGN_SECRET_MISSING: {
        'http_status': 500,
        'message': 'Signing secret missing',
        'detail': 'No HMAC signing secret is configured (SIGNING_SECRET_KEY or SECRET_KEY).',
    },
    SigningErrorCode.SIGN_EMPTY_CONTENT: {
        'http_status': 400,
        'message': 'Empty content to hash',
        'detail': 'Cannot hash empty document content for a digital signature.',
    },
    SigningErrorCode.SIGN_UNSUPPORTED_ALGORITHM: {
        'http_status': 400,
        'message': 'Unsupported signing algorithm',
        'detail': 'The requested digital signature algorithm is not supported.',
    },
    SigningErrorCode.SIGN_INVALID_BINDING: {
        'http_status': 400,
        'message': 'Invalid signature binding',
        'detail': 'The document binding or signatory context for the signature is invalid.',
    },
}


class IntegrationErrorCode(str, Enum):
    """Integraciones."""

    INT_CONNECTOR_NOT_FOUND  = 'INT_001'  # No hay conector registrado para el proveedor
    INT_CONNECTION_FAILED    = 'INT_002'  # Test de conexión fallido
    INT_TIMEOUT              = 'INT_003'  # Timeout al comunicarse con el sistema externo
    INT_PROVIDER_UNAVAILABLE = 'INT_004'  # Proveedor externo no disponible
    INT_SYNC_CONFLICT        = 'INT_005'  # Conflicto de sync resuelto a favor del WMS
    INT_DUPLICATE_IDEMPOTENT = 'INT_006'  # Operación duplicada (idempotencia)
    INT_INVALID_CREDENTIALS  = 'INT_007'  # Credenciales inválidas o expiradas
    INT_INVALID_MAPPING      = 'INT_008'  # Mapeo de datos inválido
    INT_DISABLED             = 'INT_009'  # Integraciones deshabilitadas por configuración
    INT_OAUTH_APP_NOT_FOUND  = 'INT_010'  # Aplicación OAuth de integración no encontrada
    INT_OAUTH_INVALID_SCOPE  = 'INT_011'  # Scope OAuth desconocido o inválido
    INT_OAUTH_APP_REVOKED    = 'INT_012'  # Aplicación revocada: estado terminal
    INT_OAUTH_APP_NOT_REVOKED = 'INT_013'  # Eliminar exige revocar antes
    INT_OAUTH_APP_STATE_CHANGED = 'INT_014'  # Estado cambió en paralelo (CAS fallido)
    INT_OAUTH_SCOPE_NOT_GRANTABLE = 'INT_015'  # Permiso API fuera del plan o del rol
    INT_OAUTH_SCOPE_NOT_API = 'INT_016'  # Funcionalidad que no es de categoría API


INT_REGISTRY: dict[IntegrationErrorCode, dict] = {
    IntegrationErrorCode.INT_CONNECTOR_NOT_FOUND: {
        'http_status': 404,
        'message': 'Integration connector not found',
        'detail': 'No connector is registered for the requested provider and version.',
    },
    IntegrationErrorCode.INT_CONNECTION_FAILED: {
        'http_status': 502,
        'message': 'Integration connection failed',
        'detail': 'Could not establish a connection to the external system.',
    },
    IntegrationErrorCode.INT_TIMEOUT: {
        'http_status': 504,
        'message': 'Integration timeout',
        'detail': 'The external system did not respond within the allowed time.',
    },
    IntegrationErrorCode.INT_PROVIDER_UNAVAILABLE: {
        'http_status': 502,
        'message': 'External provider unavailable',
        'detail': 'The external integration provider is temporarily unavailable.',
    },
    IntegrationErrorCode.INT_SYNC_CONFLICT: {
        'http_status': 409,
        'message': 'Integration sync conflict',
        'detail': 'A sync conflict was detected and resolved in favor of the WMS.',
    },
    IntegrationErrorCode.INT_DUPLICATE_IDEMPOTENT: {
        'http_status': 409,
        'message': 'Duplicate integration operation',
        'detail': 'This operation was already processed with the same idempotency key.',
    },
    IntegrationErrorCode.INT_INVALID_CREDENTIALS: {
        'http_status': 401,
        'message': 'Invalid integration credentials',
        'detail': 'The credentials for the external system are invalid or expired.',
    },
    IntegrationErrorCode.INT_INVALID_MAPPING: {
        'http_status': 400,
        'message': 'Invalid integration mapping',
        'detail': 'The field mapping configuration is invalid or incomplete.',
    },
    IntegrationErrorCode.INT_DISABLED: {
        'http_status': 503,
        'message': 'Integrations disabled',
        'detail': 'Integration functionality is currently disabled by configuration.',
    },
    IntegrationErrorCode.INT_OAUTH_APP_NOT_FOUND: {
        'http_status': 404,
        'message': 'Integration application not found',
        'detail': 'The requested integration application does not exist.',
    },
    IntegrationErrorCode.INT_OAUTH_INVALID_SCOPE: {
        'http_status': 400,
        'message': 'Invalid integration scope',
        'detail': 'One or more OAuth scopes are unknown or not allowed.',
    },
    IntegrationErrorCode.INT_OAUTH_APP_REVOKED: {
        'http_status': 409,
        'message': 'Integration application revoked',
        'detail': 'The integration application is revoked and can no longer be changed or reactivated.',
    },
    IntegrationErrorCode.INT_OAUTH_APP_NOT_REVOKED: {
        'http_status': 409,
        'message': 'Integration application not revoked',
        'detail': 'Revoke the integration application before deleting it.',
    },
    IntegrationErrorCode.INT_OAUTH_APP_STATE_CHANGED: {
        'http_status': 409,
        'message': 'Integration application changed',
        'detail': 'The integration application changed while the request was processed. Reload and try again.',
    },
    IntegrationErrorCode.INT_OAUTH_SCOPE_NOT_GRANTABLE: {
        'http_status': 403,
        'message': 'API permission not available',
        'detail': 'Your subscription or role does not include one or more of the selected API permissions.',
    },
    IntegrationErrorCode.INT_OAUTH_SCOPE_NOT_API: {
        'http_status': 400,
        'message': 'Only API permissions can be granted',
        'detail': 'Integration applications can only be granted API-category functionalities.',
    },
}

__all__ = [
    'StorageErrorCode',
    'IncidentErrorCode',
    'TaskMonitorErrorCode',
    'SupportSessionErrorCode',
    'AiErrorCode',
    'SigningErrorCode',
    'IntegrationErrorCode',
    'STR_REGISTRY',
    'INC_REGISTRY',
    'TASKMON_REGISTRY',
    'SSES_REGISTRY',
    'AI_REGISTRY',
    'SIGN_REGISTRY',
    'INT_REGISTRY',
]
