"""Códigos de error — tenant."""
from enum import Enum


class CompanyErrorCode(str, Enum):
    """Empresa / tenant."""

    COMPANY_NOT_FOUND      = 'COMP_001'  # Empresa no encontrada
    COMPANY_INVALID_DOMAIN = 'COMP_002'  # Dominio no corresponde a ninguna empresa
    COMPANY_DUPLICATE_NIT          = 'COMP_003'  # NIT ya asignado a otra empresa
    COMPANY_ALREADY_CLOSED         = 'COMP_004'  # Empresa ya cerrada
    COMPANY_CANNOT_REOPEN          = 'COMP_005'  # Lifecycle no permite reactivar
    COMPANY_GRACE_EXPIRED          = 'COMP_006'  # Fuera de la ventana de gracia
    COMPANY_LEGAL_HOLD             = 'COMP_007'  # Hold legal bloquea reopen/purga
    COMPANY_CLOSE_NOT_ALLOWED      = 'COMP_008'  # No se cierra el schema public
    COMPANY_PURGE_BLOCKED          = 'COMP_009'  # Purga bloqueada (hold / sin export)
    COMPANY_CLOSE_POLICY_REQUIRED  = 'COMP_010'  # Falta aceptar COMPANY-DEREGISTRATION


COMP_REGISTRY: dict[CompanyErrorCode, dict] = {
    CompanyErrorCode.COMPANY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Company not found',
        'detail': 'The requested company does not exist.',
    },
    CompanyErrorCode.COMPANY_INVALID_DOMAIN: {
        'http_status': 400,
        'message': 'Invalid domain',
        'detail': 'The provided domain does not match any registered company.',
    },
    CompanyErrorCode.COMPANY_DUPLICATE_NIT: {
        'http_status': 409,
        'message': 'Duplicate company NIT',
        'detail': 'A company with this NIT is already registered.',
    },
    CompanyErrorCode.COMPANY_ALREADY_CLOSED: {
        'http_status': 409,
        'message': 'Company already closed',
        'detail': 'This company is already closed. Reopen it during the grace period or wait for purge.',
    },
    CompanyErrorCode.COMPANY_CANNOT_REOPEN: {
        'http_status': 409,
        'message': 'Company cannot be reopened',
        'detail': 'Only a closed company in the grace window can be reopened.',
    },
    CompanyErrorCode.COMPANY_GRACE_EXPIRED: {
        'http_status': 409,
        'message': 'Reopen window has expired',
        'detail': 'The grace period to reopen this company has ended. Register a new company if you need access again.',
    },
    CompanyErrorCode.COMPANY_LEGAL_HOLD: {
        'http_status': 409,
        'message': 'Company is on legal hold',
        'detail': 'This company has a legal hold. Resolve the hold before reopening or purging.',
    },
    CompanyErrorCode.COMPANY_CLOSE_NOT_ALLOWED: {
        'http_status': 400,
        'message': 'This tenant cannot be closed',
        'detail': 'The platform tenant cannot be closed. Choose a customer company.',
    },
    CompanyErrorCode.COMPANY_PURGE_BLOCKED: {
        'http_status': 409,
        'message': 'Company purge is blocked',
        'detail': 'Purge is blocked by a legal hold or a missing export record. Resolve that before deleting the tenant.',
    },
    CompanyErrorCode.COMPANY_CLOSE_POLICY_REQUIRED: {
        'http_status': 400,
        'message': 'Company deregistration policy must be accepted',
        'detail': 'Accept the published COMPANY-DEREGISTRATION policy for this country before closing the company.',
    },
}


class OnboardingErrorCode(str, Enum):
    """Onboarding."""

    ONBOARDING_NOT_FOUND                = 'ONB_001'  # Registro de onboarding no encontrado o expirado
    ONBOARDING_EXPIRED                  = 'ONB_002'  # El proceso de onboarding ha expirado
    ONBOARDING_ALREADY_COMPLETED        = 'ONB_003'  # El proceso ya fue finalizado
    ONBOARDING_STEP_OUT_OF_ORDER        = 'ONB_004'  # Intento de avanzar sin completar el step previo
    ONBOARDING_DUPLICATE_EMAIL          = 'ONB_005'  # Ya existe un onboarding activo con ese email
    ONBOARDING_DUPLICATE_NIT            = 'ONB_006'  # Ya existe un onboarding activo con ese NIT
    ONBOARDING_INVALID_TOKEN            = 'ONB_007'  # Token de onboarding ausente o inválido
    ONBOARDING_SCHEMA_TAKEN             = 'ONB_008'  # Nombre de schema ya está en uso
    ONBOARDING_INVALID_PLAN             = 'ONB_009'  # Plan de suscripción inexistente o inactivo
    ONBOARDING_PAYMENT_REQUIRED         = 'ONB_010'  # El plan seleccionado requiere método de pago
    ONBOARDING_EMAIL_ALREADY_REGISTERED = 'ONB_011'  # Ya existe una cuenta de usuario con ese correo
    ONBOARDING_RESEND_THROTTLED         = 'ONB_012'  # Reenvío de enlace bloqueado por ventana de throttle
    ONBOARDING_PRIVACY_REQUIRED         = 'ONB_013'  # Debe aceptar la política de privacidad publicada
    ONBOARDING_PRIVACY_STALE            = 'ONB_014'  # Hash/país no coincide con la versión liberada
    ONBOARDING_TERMS_REQUIRED           = 'ONB_015'  # Debe aceptar los términos y condiciones publicados
    ONBOARDING_TERMS_STALE              = 'ONB_016'  # Hash de términos no coincide con la versión liberada


ONB_REGISTRY: dict[OnboardingErrorCode, dict] = {
    OnboardingErrorCode.ONBOARDING_NOT_FOUND: {
        'http_status': 404,
        'message': 'Onboarding not found',
        'detail': 'The onboarding process could not be located. Please start again.',
    },
    OnboardingErrorCode.ONBOARDING_EXPIRED: {
        'http_status': 410,
        'message': 'Onboarding expired',
        'detail': 'Your onboarding session has expired. Please start the registration again.',
    },
    OnboardingErrorCode.ONBOARDING_ALREADY_COMPLETED: {
        'http_status': 409,
        'message': 'Onboarding already completed',
        'detail': 'This registration has already been completed. Please sign in.',
    },
    OnboardingErrorCode.ONBOARDING_STEP_OUT_OF_ORDER: {
        'http_status': 409,
        'message': 'Step out of order',
        'detail': 'You must complete previous steps before reaching this one.',
    },
    OnboardingErrorCode.ONBOARDING_DUPLICATE_EMAIL: {
        'http_status': 409,
        'message': 'Duplicate email',
        'detail': 'An active registration already exists for this email address.',
    },
    OnboardingErrorCode.ONBOARDING_DUPLICATE_NIT: {
        'http_status': 409,
        'message': 'Duplicate company NIT',
        'detail': 'A company with this NIT is already registered or in progress.',
    },
    OnboardingErrorCode.ONBOARDING_INVALID_TOKEN: {
        'http_status': 401,
        'message': 'Invalid onboarding token',
        'detail': 'The onboarding token is missing, invalid, or has expired.',
    },
    OnboardingErrorCode.ONBOARDING_SCHEMA_TAKEN: {
        'http_status': 409,
        'message': 'Schema name taken',
        'detail': 'The derived company identifier is already in use. Please choose a different company name.',
    },
    OnboardingErrorCode.ONBOARDING_INVALID_PLAN: {
        'http_status': 400,
        'message': 'Invalid subscription plan',
        'detail': 'The selected subscription plan does not exist or is not available.',
    },
    OnboardingErrorCode.ONBOARDING_PAYMENT_REQUIRED: {
        'http_status': 400,
        'message': 'Payment required',
        'detail': 'The selected plan requires a valid payment method before finalizing.',
    },
    OnboardingErrorCode.ONBOARDING_EMAIL_ALREADY_REGISTERED: {
        'http_status': 409,
        'message': 'Email already registered',
        'detail': 'An account with this email already exists. Please sign in instead.',
    },
    OnboardingErrorCode.ONBOARDING_RESEND_THROTTLED: {
        'http_status': 429,
        'message': 'Resend throttled',
        'detail': 'You requested a new link too soon. Please wait a moment before trying again.',
    },
    OnboardingErrorCode.ONBOARDING_PRIVACY_REQUIRED: {
        'http_status': 400,
        'message': 'Privacy policy acceptance required',
        'detail': 'You must accept the published privacy policy before completing registration.',
    },
    OnboardingErrorCode.ONBOARDING_PRIVACY_STALE: {
        'http_status': 409,
        'message': 'Privacy policy outdated',
        'detail': 'The privacy policy you reviewed is no longer the published version. Reload and accept again.',
    },
    OnboardingErrorCode.ONBOARDING_TERMS_REQUIRED: {
        'http_status': 400,
        'message': 'Terms and conditions acceptance required',
        'detail': 'You must accept the published terms and conditions before completing registration.',
    },
    OnboardingErrorCode.ONBOARDING_TERMS_STALE: {
        'http_status': 409,
        'message': 'Terms and conditions outdated',
        'detail': 'The terms and conditions you reviewed are no longer the published version. Reload and accept again.',
    },
}

__all__ = ['CompanyErrorCode', 'OnboardingErrorCode', 'COMP_REGISTRY', 'ONB_REGISTRY']
