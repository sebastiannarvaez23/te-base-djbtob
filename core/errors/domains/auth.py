"""Códigos de error — auth."""
from enum import Enum


class AuthErrorCode(str, Enum):
    """Autenticación y sesión."""

    AUTH_INVALID_CREDENTIALS = 'AUTH_001'  # Usuario o contraseña incorrectos
    AUTH_ROLE_DISABLED       = 'AUTH_002'  # El rol del usuario está inactivo
    AUTH_ACCOUNT_INACTIVE    = 'AUTH_003'  # La cuenta del usuario está inactiva
    AUTH_TOKEN_INVALID       = 'AUTH_004'  # Token ausente, inválido o expirado
    AUTH_TOKEN_REQUIRED      = 'AUTH_005'  # Se requiere autenticación
    AUTH_COMPANY_SUSPENDED   = 'AUTH_006'  # La empresa del usuario está suspendida
    AUTH_EMAIL_NOT_VERIFIED  = 'AUTH_007'  # El correo del usuario aún no ha sido confirmado
    AUTH_APP_INACTIVE        = 'AUTH_008'  # Aplicación de integración inactiva o revocada
    AUTH_UNSUPPORTED_GRANT   = 'AUTH_009'  # grant_type OAuth no soportado
    AUTH_SCOPE_DENIED        = 'AUTH_010'  # Scope solicitado no concedido a la aplicación
    AUTH_OTP_INVALID         = 'AUTH_011'  # Código 2FA incorrecto
    AUTH_OTP_EXPIRED         = 'AUTH_012'  # Desafío 2FA ausente o expirado
    AUTH_OTP_LOCKED          = 'AUTH_013'  # Demasiados intentos de código 2FA
    AUTH_DEVICE_NOT_FOUND    = 'AUTH_014'  # Dispositivo de confianza no encontrado
    AUTH_PASSWORD_EXPIRED    = 'AUTH_015'  # La contraseña caducó y debe cambiarse
    AUTH_PASSWORD_REUSED     = 'AUTH_016'  # La contraseña coincide con una reciente
    AUTH_LOGIN_LOCKED        = 'AUTH_017'  # Demasiados intentos de contraseña
    AUTH_SESSION_EXISTS      = 'AUTH_018'  # Ya hay una sesión activa (MULTI_SESSIONS off)
    AUTH_COMPANY_CLOSED      = 'AUTH_019'  # Empresa dada de baja (CLOSED / PENDING_PURGE)
    AUTH_SESSION_IDLE        = 'AUTH_020'  # Sesión cerrada por tiempo de inactividad


AUTH_REGISTRY: dict[AuthErrorCode, dict] = {
    AuthErrorCode.AUTH_INVALID_CREDENTIALS: {
        'http_status': 401,
        'message': 'Invalid credentials',
        'detail': 'The username or password is incorrect.',
    },
    AuthErrorCode.AUTH_ROLE_DISABLED: {
        'http_status': 403,
        'message': 'Role disabled',
        'detail': 'The role assigned to this user is disabled. Please contact your administrator.',
    },
    AuthErrorCode.AUTH_ACCOUNT_INACTIVE: {
        'http_status': 403,
        'message': 'Account inactive',
        'detail': 'This user account has been disabled. Please contact your administrator.',
    },
    AuthErrorCode.AUTH_TOKEN_INVALID: {
        'http_status': 401,
        'message': 'Invalid token',
        'detail': 'The authentication token is invalid or has expired.',
    },
    AuthErrorCode.AUTH_TOKEN_REQUIRED: {
        'http_status': 401,
        'message': 'Authentication required',
        'detail': 'Authentication is required to access this resource.',
    },
    AuthErrorCode.AUTH_COMPANY_SUSPENDED: {
        'http_status': 403,
        'message': 'Company suspended',
        'detail': 'The company associated with this account is currently suspended. Please contact your administrator.',
    },
    AuthErrorCode.AUTH_EMAIL_NOT_VERIFIED: {
        'http_status': 403,
        'message': 'Email not verified',
        'detail': 'You must confirm your email address before signing in. Check your inbox or request a new confirmation message.',
    },
    AuthErrorCode.AUTH_APP_INACTIVE: {
        'http_status': 403,
        'message': 'Integration application inactive',
        'detail': 'This integration application is disabled or revoked.',
    },
    AuthErrorCode.AUTH_UNSUPPORTED_GRANT: {
        'http_status': 400,
        'message': 'Unsupported grant type',
        'detail': 'Only the client_credentials grant type is supported for integration applications.',
    },
    AuthErrorCode.AUTH_SCOPE_DENIED: {
        'http_status': 403,
        'message': 'Scope not granted',
        'detail': 'One or more requested scopes are not granted to this integration application.',
    },
    AuthErrorCode.AUTH_OTP_INVALID: {
        'http_status': 400,
        'message': 'Invalid verification code',
        'detail': 'The two-factor verification code is incorrect.',
    },
    AuthErrorCode.AUTH_OTP_EXPIRED: {
        'http_status': 400,
        'message': 'Verification expired',
        'detail': 'The two-factor verification session has expired. Sign in again.',
    },
    AuthErrorCode.AUTH_OTP_LOCKED: {
        'http_status': 429,
        'message': 'Too many verification attempts',
        'detail': 'Too many incorrect verification codes were submitted. Sign in again.',
    },
    AuthErrorCode.AUTH_DEVICE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Trusted device not found',
        'detail': 'That trusted device does not exist or was already revoked.',
    },
    AuthErrorCode.AUTH_PASSWORD_EXPIRED: {
        'http_status': 403,
        'message': 'Password expired',
        'detail': 'Your password has expired. Choose a new password to continue.',
    },
    AuthErrorCode.AUTH_PASSWORD_REUSED: {
        'http_status': 400,
        'message': 'Password recently used',
        'detail': 'That password was used recently. Choose a different password.',
    },
    AuthErrorCode.AUTH_LOGIN_LOCKED: {
        'http_status': 429,
        'message': 'User locked',
        'detail': 'Your user has been locked after too many failed login attempts. Try again later.',
    },
    AuthErrorCode.AUTH_SESSION_EXISTS: {
        'http_status': 409,
        'message': 'Session already active',
        'detail': 'You already have an active session. Sign out on the other device to continue.',
    },
    AuthErrorCode.AUTH_COMPANY_CLOSED: {
        'http_status': 403,
        'message': 'Company closed',
        'detail': 'This company has been closed. Contact the base if you need to reopen it during the grace period.',
    },
    AuthErrorCode.AUTH_SESSION_IDLE: {
        'http_status': 401,
        'message': 'Session idle',
        'detail': 'You were signed out after a period of inactivity. Sign in again.',
    },
}

__all__ = ['AuthErrorCode', 'AUTH_REGISTRY']
